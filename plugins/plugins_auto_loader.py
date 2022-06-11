
import time

from locator import Locator, Update, LocatorEvent

class LoaderSystem:

	tags = {"plugin_aauto_loader"}

	def __init__(self):

		self._last = time.time()

	def on_event(self, event: LocatorEvent):

		now = time.time()

		if isinstance(event, Update) and (now - self._last) > 30:

			self._last = now
			Locator.load_plugins()

tags = {"plugins_auto_loader"}

def initialize():

	loader_system = LoaderSystem()
	Locator.add_system(loader_system)
	Locator.add_observer(loader_system)
