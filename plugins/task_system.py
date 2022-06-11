
from __future__ import annotations

import json
import shutil
import time
from typing import Iterable, Optional
import tweepy#type: ignore

from dataclasses import dataclass
from pathlib import Path

from locator import Update, LocatorEvent, Locator, Exit
from plugin_loader import assert_tags
from event import Event, Error
from herald import Herald
from protocols import SystemProtocol
from tag import PluginTag
from cast_tools import CasterFactory

import plugins.task_system_config as task_system_config
from plugins.data_system_protocols import DataSystemProtocol

class CannotLocateDataSystem(Exception): ...
class CannotLocateTaskSystem(Exception): ...

def locate_data_system() -> DataSystemProtocol:

	ans = Locator.get_system({"data_system"})
	if ans is None: raise CannotLocateDataSystem()
	else: return CasterFactory[SystemProtocol, DataSystemProtocol]()(ans)

def locate_task_system() -> TaskSystem:

	ans = Locator.get_system({"task_system"})
	if ans is None: raise CannotLocateTaskSystem()
	else: return CasterFactory[SystemProtocol, TaskSystem]()(ans)

class Task:

	def check(self) -> bool:
		"""returns True if the task is worthy of running"""
		return True

	def run(self):
		pass

	def save(self) -> str:
		return repr(self)

	@staticmethod
	def load(saved: str) -> Task:
		return eval(saved)

def tweet_is_on_topic(tweet: tweepy.Tweet) -> bool:

	text = str(tweet.text).lower()
	return any(keyword in text for keyword in task_system_config.keywords)

def is_retweet(tweet: tweepy.Tweet) -> Optional[int]:

	if tweet.referenced_tweets is None: return None

	for ref in tweet.referenced_tweets:
		if ref["type"] == "retweeted" or ref["type"] == "quoted":
			return int(ref["id"])

	return None

def get_mentions(tweet: tweepy.Tweet) -> Iterable[str]:

	if tweet.entities is None:
		return []

	try:
		mentions_dat = tweet.entities["mentions"]

	except KeyError:
		return []

	else:
		return (e["username"] for e in mentions_dat)

class TaskEvent(Event): ...
class TaskError(Error, TaskEvent): ...

@dataclass
class FirstSightUser(Task):
	"""Checks if any tweet is on topic and starts processing user accordingly"""

	id: int

	def check(self) -> bool:
		return not locate_data_system().is_processed(self.id)

	def run(self):

		data_system = locate_data_system()
		task_system = locate_task_system()

		if (user := data_system.get_user(self.id)) is None:
			return

		for tweet_id in data_system.get_recent_tweets(self.id):
			if (tweet := data_system.get_tweet(tweet_id)) is not None:
				if tweet_is_on_topic(tweet):
					task_system.put_task(ScanUser(id=self.id))
					break

		data_system.tag_processed(self.id)

@dataclass
class ScanUser(Task):
	"""Procedes to full scan of user, assuming they are on topic"""

	id: int

	def run(self):

		data_system = locate_data_system()
		task_system = locate_task_system()

		for tweet_id in data_system.get_recent_tweets(self.id):
			task_system.put_task(ScanTweet(id=tweet_id))

		task_system.put_task(FollowersProcess(id=self.id))

@dataclass
class FirstSightTweet(Task):
	"""Checks if the tweet is on topic, and create appropriate tasks"""

	id: int

	def check(self) -> bool:
		return not locate_data_system().is_tweet_processed(self.id)

	def run(self):

		data_system = locate_data_system()
		task_system = locate_task_system()

		if (tweet := data_system.get_tweet(self.id)) is None:
			return

		if tweet_is_on_topic(tweet):
			task_system.put_task(ScanTweet(id=self.id))

		if (tweet_id := is_retweet(tweet)) is not None:
			task_system.put_task(FirstSightTweet(id=tweet_id))

		data_system.tag_tweet_processed(self.id)

@dataclass
class ScanTweet(Task):
	"""Creates appropriate tasks, assuming the tweet's author is on topic"""

	id: int

	def run(self):
		
		data_system = locate_data_system()
		task_system = locate_task_system()

		if (tweet := data_system.get_tweet(self.id)) is None:
			return

		task_system.put_task(FirstSightUser(id=int(tweet.author_id)))
		task_system.put_task(MentionsProcess(id=self.id))

@dataclass
class MentionsProcess(Task):
	"""Checks mentions and starts processing of mentionned users, assuming the author is on topic"""

	id: int

	def run(self):

		data_system = locate_data_system()
		task_system = locate_task_system()

		if (tweet := data_system.get_tweet(self.id)) is None:
			return

		for username in get_mentions(tweet):
			if (user_id := data_system.get_id(username)) is not None:
				task_system.put_task(FirstSightUser(id=user_id))

@dataclass
class FollowersProcess(Task):
	"""Checks followers and process users, assuming the followed is on topic"""

	id: int

	def run(self):

		data_system = locate_data_system()
		task_system = locate_task_system()

		for follower_id in data_system.get_followers(self.id):
			task_system.put_task(FirstSightUser(id=follower_id))

def archive_task_file(file: Path):
	shutil.copy(file, task_system_config.tasks_archive_dir/f"{time.time()}.json")

class TaskSystemEvent(Event): ...
class TaskSystemError(Error, TaskSystemEvent): ...

@dataclass
class AddedTask(TaskSystemEvent):

	task: Task

@dataclass
class WorkingOnTask(TaskSystemEvent):

	task: Task

@dataclass
class ShuttingDown(TaskSystemEvent):
	...

@dataclass
class DumpedTasks(TaskSystemEvent):

	amount: int

@dataclass
class LoadedTasks(TaskSystemEvent):

	amount: int

@dataclass
class ChargeReport(TaskSystemEvent):

	pending_tasks: int

class TaskSystem(Herald[TaskSystemEvent]):

	tags = {"task_system",}

	def __init__(self):

		Herald.__init__(self)
		self._tasks: list[Task] = []

		if task_system_config.tasks_file.exists():

			self._load_tasks(task_system_config.tasks_file)
			self._dispatch_event(LoadedTasks(amount=len(self._tasks)))
			archive_task_file(task_system_config.tasks_file)
			task_system_config.tasks_file.unlink()

	def on_event(self, event: LocatorEvent):

		if isinstance(event, Update):
			self._tick()

		if isinstance(event, Exit):

			self._dispatch_event(ShuttingDown())

			if self._tasks:
				self._save_tasks(task_system_config.tasks_file)
				self._dispatch_event(DumpedTasks(amount=len(self._tasks)))

	def _save_tasks(self, file: Path):
		json.dump([task.save() for task in self._tasks], open(file, "w", encoding="utf-8"), indent=4)

	def _load_tasks(self, file: Path):
		self._tasks = [Task.load(saved) for saved in json.load(open(file, "r", encoding="utf-8"))]

	def _tick(self):

		if self._tasks:

			if self._tasks[0].check():
				self._dispatch_event(WorkingOnTask(task=self._tasks[0]))
				self._tasks[0].run()

			self._tasks.pop(0)
			self._dispatch_event(ChargeReport(pending_tasks=len(self._tasks)))

	def put_task(self, task: Task):

		self._tasks.append(task)
		self._dispatch_event(AddedTask(task=task))
		self._dispatch_event(ChargeReport(pending_tasks=len(self._tasks)))

tags = {"task_system"}

def initialize():

	assert_tags(existing=Locator.loaded_tags, required={"data_system"})
	task_system = TaskSystem()
	Locator.add_observer(task_system)
	Locator.add_system(task_system)
