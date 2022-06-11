
from __future__ import annotations
from typing import Protocol

from locator import SystemProtocol
from herald import HeraldProtocol
from plugins.task_system import TaskSystemEvent

class TaskProtocol(Protocol):

	def run(self): ...
	def save(self) -> str: ...
	@staticmethod
	def load(saved: str) -> TaskProtocol: ...

class TaskSystemProtocol(SystemProtocol, HeraldProtocol[TaskSystemEvent], Protocol):

	def put_task(self, task: TaskProtocol): ...
