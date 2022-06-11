
from dataclasses import dataclass
import time
from typing import TypeVar

from rich.console import Console
from datetime import datetime

import plugins.log_system_config as log_system_config

from event import Event
from locator import Update, Error, Exit, Locator
from protocols import SystemProtocol
from tag import SystemTag
from plugins.task_system_protocols import TaskSystemProtocol
from plugins.data_system_protocols import DataSystemProtocol
from cast_tools import CasterFactory
from plugin_loader import assert_tags

@dataclass
class CannotLocateSystem(Exception):

	system_tag: SystemTag

T = TypeVar("T", bound=SystemProtocol)

def locate_system(tag: SystemTag) -> SystemProtocol:

	ans = Locator.get_system({tag,})
	if ans is None: raise CannotLocateSystem(tag)
	else: return ans

class LogSystem:

	tags = {"log_system"}

	def __init__(self):

		self._console = Console(record=True)
		self._colors = ["blue", "cyan", "green", "purple", "yellow"]
		self._color_map: dict[str, str] = {}

	def _get_new_color(self) -> str:

		if len(self._colors) == 1:
			return self._colors[0]

		else:
			return self._colors.pop()

	def _get_color(self, name: str) -> str:

		try:
			return self._color_map[name]

		except KeyError:

			self._color_map[name] = self._get_new_color()
			return self._color_map[name]

	def _archive(self):

		with open(log_system_config.logs_dir/f"{time.time()}.html", "w", encoding="utf-8") as f:
			f.write(self._console.export_html())

	def on_event(self, event: Event):

		if isinstance(event, Update):
			return

		style = "red" if isinstance(event, Error) else "normal"
		parent_name = event.__class__.__mro__[1].__name__
		parent_color = self._get_color(parent_name)
		self._console.print(f"[dim]{datetime.now()}...[/dim][{parent_color}]{parent_name}[/{parent_color}]...[{style}]{event}[/{style}]")

		if isinstance(event, Exit):
			self._archive()

tags = {"log_system"}

def initialize():

	assert_tags(existing=Locator.loaded_tags, required={"task_system", "data_system"})
	log_system = LogSystem()
	CasterFactory[SystemProtocol, TaskSystemProtocol]()(locate_system("task_system")).add_observer(log_system)
	CasterFactory[SystemProtocol, DataSystemProtocol]()(locate_system("data_system")).add_observer(log_system)
	Locator.add_observer(log_system)
