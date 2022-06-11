
from typing import Callable, TypeVar

T = TypeVar("T")

class FactoryType:

	def __init__(self):

		self._creators: dict[str, Callable] = {}

	def set(self, name: str, creator: Callable):
		self._creators[name] = creator

	def rem(self, name: str):
		self._creators.pop(name)

	def create(self, name: str, t: type[T], *args, **kwargs) -> T:
		return self._creators[name](*args, **kwargs)

Factory = FactoryType()
