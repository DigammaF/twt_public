
from __future__ import annotations

import sqlite3
import time
import requests
import json
import tweepy #type: ignore

from pathlib import Path
from typing import Any, Callable, Iterable, Optional, TypeVar

import plugins.data_system_config as data_system_config

from event import Event, Error
from herald import Herald
from locator import Locator

DefaultType = TypeVar("DefaultType")

class Database:

	def __init__(self, file: Path) -> None:
		
		self._connector = sqlite3.connect(file)
		self._cursor = self._connector.cursor()

	def exec(self, sql: str, params: dict[str, Any] = {}):

		self._cursor.execute(sql, params)
		self._connector.commit()

	def fetch(self, sql: str, params: dict[str, Any] = {}) -> list:

		self._cursor.execute(sql, params)
		return list(self._cursor.fetchall())

	def fetch_one(self,
		sql: str, params: dict[str, Any] = {},
		default: DefaultType = None) -> Optional[DefaultType]:

		for e in self.fetch(sql, params):
			return e

		return default

def read_api_login_file(name: str) -> str:

	with open(data_system_config.api_login_dir/name, "r", encoding="utf-8") as f:
		return f.read()

def get_data(answer: requests.Response) -> Optional[dict]:

	if not answer.status_code == 200: return None

	try:
		data = answer.json()["data"]

	except KeyError:
		return None

	return data

def get_meta(answer: requests.Response) -> Optional[dict]:

	if not answer.status_code == 200: return None

	try:
		meta = answer.json()["meta"]

	except KeyError:
		return None

	return meta

T = TypeVar("T")

class DataSystemEvent(Event): ...
class DataSystemError(Error, DataSystemEvent): ...

class TwitterConnectionError(DataSystemError): ...

class DataSystem(Herald[DataSystemEvent]):
	"""Provides cached interface with twitter api"""

	tags = {"data_system", "tweet_data", "user_data", "username_conversion"}

	def __init__(self):

		Herald.__init__(self)
		self._database = Database(data_system_config.data_system_file)
		self._database.exec(
			"CREATE TABLE IF NOT EXISTS users ("
			"id integer, username text, processed integer, data text"
			")"
		)
		self._database.exec(
			"CREATE TABLE IF NOT EXISTS tweets ("
			"id integer, author integer, processed integer, data text"
			")"
		)
		self._database.exec(
			"CREATE TABLE IF NOT EXISTS follows ("
			"actor integer, target integer"
			")"
		)
		self._api: tweepy.Client = tweepy.Client(
			consumer_key=read_api_login_file("api_key.txt"),
			consumer_secret=read_api_login_file("api_key_secret.txt"),
			access_token=read_api_login_file("access_token.txt"),
			access_token_secret=read_api_login_file("access_token_secret.txt"),
			bearer_token=read_api_login_file("bearer_token.txt"),
			wait_on_rate_limit=True,
			return_type=requests.Response,
		)

	def _api_call(self, f: Callable[..., T], *args, **kwargs) -> T:

		try:
			return f(*args, **kwargs)

		except tweepy.TwitterServerError:

			self._dispatch_event(TwitterConnectionError())
			time.sleep(30)
			return self._api_call(f, *args, **kwargs)

	def is_processed(self, user_id: int) -> bool:
		return bool(self._get(bool, "users", user_id, "processed"))

	def tag_processed(self, user_id: int):
		self._database.exec(
			f"UPDATE users SET processed = 1 WHERE id = :id", {"id": user_id}
		)

	def is_tweet_processed(self, tweet_id: int) -> bool:
		return bool(self._get(bool, "tweets", tweet_id, "processed"))

	def tag_tweet_processed(self, tweet_id: int):
		self._database.exec(
			f"UPDATE tweets SET processed = 1 WHERE id = :id", {"id": tweet_id}
		)

	def get_followers(self, user_id: int) -> Iterable[int]:
		
		pagination_token = None

		while True:

			if (ans := self._api_call(self._api.get_users_followers, id=user_id, pagination_token=pagination_token, user_fields=["public_metrics", "username"])) is None:
				break

			data, meta = get_data(ans), get_meta(ans)

			if data is None or meta is None:
				break

			for user_data in data:
				self._set_user(tweepy.User(user_data))
				self._database.exec("INSERT INTO follows VALUES (:actor, :target)", {"actor": int(user_data["id"]), "target": user_id})
				yield int(user_data["id"])

			try:
				pagination_token = meta["next_token"]

			except KeyError:
				break

	def get_recent_tweets(self, user_id: int) -> Iterable[int]:
		
		if (ans := self._api_call(self._api.get_users_tweets, id=user_id, tweet_fields=["entities", "referenced_tweets", "author_id"])) is None:
			return

		if (data := get_data(ans)) is None:
			return

		for tweet_data in data:
			self._set_tweet(tweepy.Tweet(tweet_data))
			yield int(tweet_data["id"])

	def get_id(self, username: str) -> Optional[int]:

		ans = self._database.fetch_one("SELECT id FROM users WHERE username = :username", {"username": username})
		
		if ans is None:
			if (data := get_data(self._api_call(self._api.get_user, username=username, user_fields=["public_metrics", "username"]))) is None:
				return None

			else:
				self._set_user(tweepy.User(data))
				return int(data["id"])

		else:
			(id,) = ans
			return int(id)

	def _get(self, t: type[T], /, table: str, id: int, attr: str) -> Optional[T]:

		ans = self._database.fetch_one(
			f"SELECT {attr} FROM {table} WHERE id = :id",
			{"id": id},
		)

		if ans is None:
			return None

		else:

			(val,) = ans
			return val #type: ignore

	def _get_user(self, id: int) -> Optional[tweepy.User]:

		if (data := self._get(str, "users", id, "data")) is None:
			return None

		else:
			return tweepy.User(json.loads(data))

	def _set_user(self, user: tweepy.User):

		self._database.exec(
			"INSERT INTO users VALUES (:id, :username, 0, :data)",
			{"id": int(user.id), "data": json.dumps(user.data), "username": user.username}
		)

	def get_user(self, id: int) -> Optional[tweepy.User]:
		
		if (user := self._get_user(id)) is None:
			if (data := get_data(self._api_call(self._api.get_user, id=id, user_fields=["public_metrics", "username"]))) is None:
				return None

			else:

				user = tweepy.User(data)
				self._set_user(user)
				return user

		else:
			return user

	def _get_tweet(self, id: int) -> Optional[tweepy.Tweet]:

		if (data := self._get(str, "tweets", id, "data")) is None:
			return None

		else:
			return tweepy.Tweet(json.loads(data))

	def _set_tweet(self, tweet: tweepy.Tweet):

		self._database.exec(
			"INSERT INTO tweets VALUES (:id, :author, 0, :data)",
			{"id": int(tweet.id), "data": json.dumps(tweet.data), "author": int(tweet.author_id)}
		)

	def get_tweet(self, id: int) -> Optional[tweepy.Tweet]:
		
		if (tweet := self._get_tweet(id)) is None:
			if (data := get_data(self._api_call(self._api.get_tweet, id=id, tweet_fields=["entities", "referenced_tweets", "author_id"]))) is None:
				return None

			else:

				tweet = tweepy.Tweet(data)
				self._set_tweet(tweet)
				return tweet

		else:
			return tweet

tags = {"data_system"}

def initialize():

	Locator.add_system(DataSystem())
