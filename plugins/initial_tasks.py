
import json

from cast_tools import CasterFactory
from locator import Locator
from plugin_loader import assert_tags
from plugins.task_system import CannotLocateTaskSystem, TaskSystem, FirstSightTweet, FirstSightUser
from protocols import SystemProtocol

import plugins.initial_tasks_config as initial_tasks_config

def locate_task_system() -> TaskSystem:

	ans = Locator.get_system({"task_system"})
	if ans is None: raise CannotLocateTaskSystem()
	else: return CasterFactory[SystemProtocol, TaskSystem]()(ans)

tags = {"initial_tasks"}

def initialize():

	assert_tags(existing=Locator.loaded_tags, required={"task_system", "log_system"})
	task_system = locate_task_system()
	ids = json.load(open(initial_tasks_config.ids_file, "r", encoding="utf-8"))

	for id in ids["users"]:
		task_system.put_task(FirstSightUser(id=int(id)))

	for id in ids["tweets"]:
		task_system.put_task(FirstSightTweet(id=int(id)))
