
import importlib
from pathlib import Path
from typing import TypeAlias

import config

from tag import PluginTag

PluginName: TypeAlias = str

class MissingTags(Exception):

	def __init__(self, tags: frozenset[PluginTag]):

		self.tags = tags

class PluginNotFound(Exception):

	def __init__(self, name: PluginName):

		self.name = name

class Plugin:

	tags: frozenset[PluginTag]

	@staticmethod
	def initialize(): ...

def _get_plugin_path(name: PluginName) -> str:
	return f"{config.plugins_package}.{name}"

def _get_plugin(name: PluginName) -> Plugin:

	try:
		return importlib.import_module(_get_plugin_path(name)) #type: ignore

	except ModuleNotFoundError as e:
		raise PluginNotFound(name) from e

def assert_tags(existing: frozenset[PluginTag], required: frozenset[PluginTag]):

	if (missing := required - existing):
		raise MissingTags(missing)

def load_plugin(name: PluginName) -> Plugin:
	
	plugin = _get_plugin(name)
	plugin.initialize()
	return plugin
