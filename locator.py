
import json
import hashlib
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, TypeAlias, TypeVar

import config

from event import Error, Event
from herald import Herald
from plugin_loader import MissingTags, PluginName, PluginNotFound, load_plugin
from tag import PluginTag, SystemTag
from protocols import SystemProtocol

class EnsureCall:

	def __init__(self, f: Callable):

		self._f = f

	def __enter__(self):
		return self

	def __exit__(self, *args, **kwargs):
		self._f()

class LocatorEvent(Event): ...
class LocatorError(Error, LocatorEvent): ...

@dataclass
class LoadedPlugin(LocatorEvent):

	plugin_name: str

@dataclass
class MissingPlugin(LocatorError):

	plugin_name: PluginName

@dataclass
class CannotLoadPlugins(LocatorError):

	plugin_names: list[PluginName]
	missing_tags: list[PluginTag]

@dataclass
class CannotReadPluginsFile(LocatorError):
	...

@dataclass
class AddedSystem(LocatorEvent):
	
	system_name: str
	system: SystemProtocol

@dataclass
class RemovedSystem(LocatorEvent):

	system_name: str

class Update(LocatorEvent):
	...

@dataclass
class Exit(LocatorEvent):
	...

T = TypeVar("T", bound=SystemProtocol)

class LocatorType(Herald[LocatorEvent]):

	def __init__(self) -> None:

		super().__init__()
		self.loaded_plugins: set[PluginName] = set()
		self.loaded_tags: set[PluginTag] = set()
		self._plugins_file_hash: str = "no hash"
		self._systems: list[SystemProtocol] = []
		self._keep_going: bool = True

	def shutdown(self):
		self._keep_going = False

	def main_loop(self):

		with EnsureCall(self._on_exit):
			while self._keep_going:
				self._dispatch_event(Update())

	def _on_exit(self):

		self._dispatch_event(Exit())

	def get_system(self, tags: set[SystemTag]) -> Optional[SystemProtocol]:

		for system in self._systems:
			if all(tag in system.tags for tag in tags):
				return system

		return None

	def get_systems(self, tags: set[SystemTag]) -> Iterable[SystemProtocol]:

		for system in self._systems:
			if all(tag in system.tags for tag in tags):
				yield system

	def add_system(self, system: SystemProtocol):

		self._systems.append(system)
		self._dispatch_event(AddedSystem(system_name=system.__class__.__name__, system=system))

	def rem_system(self, system: SystemProtocol):

		try:
			self._systems.remove(system)

		except ValueError:
			pass

		else:
			self._dispatch_event(RemovedSystem(system_name=system.__class__.__name__))

	def load_plugins(self):
		
		with open(config.plugins_file, "r", encoding="utf-8") as f:
			content = f.read()

		hasher = hashlib.md5()
		hasher.update(content.encode(encoding="utf-8"))
		file_hash = hasher.hexdigest()

		if file_hash == self._plugins_file_hash:
			return

		self._plugins_file_hash = file_hash

		try:
			plugin_names: set[PluginName] = set(json.loads(content)) - self.loaded_plugins

		except json.decoder.JSONDecodeError:
			self.events.dispatch(CannotReadPluginsFile())
			return

		missing_tags: set[PluginTag] = set()

		while plugin_names:

			local_plugin_names = plugin_names.copy()
			prev_missing_tags = missing_tags
			missing_tags = set()

			while local_plugin_names:

				plugin_name = local_plugin_names.pop()

				try:
					plugin = load_plugin(plugin_name)

				except PluginNotFound:
					
					self._dispatch_event(MissingPlugin(plugin_name=plugin_name))
					plugin_names.remove(plugin_name)
					continue

				except MissingTags as e:

					missing_tags |= e.tags
					continue

				else:

					self._dispatch_event(LoadedPlugin(plugin_name=plugin_name))
					plugin_names.remove(plugin_name)
					self.loaded_tags |= plugin.tags
					print(f"loaded {plugin_name}")

			if missing_tags and missing_tags == prev_missing_tags:

				print(f"cannot load {plugin_name=}, {missing_tags=}")
				self._dispatch_event(
					CannotLoadPlugins(
						plugin_names=list(plugin_names),
						missing_tags=list(missing_tags),
					)
				)
				return

Locator = LocatorType()
