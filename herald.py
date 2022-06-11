
from typing import TypeVar, Generic, Protocol

T = TypeVar("T", contravariant=True)

class ObserverProtocol(Protocol, Generic[T]):

	def on_event(self, event: T): pass

EvT = TypeVar("EvT", covariant=True)

class HeraldProtocol(Generic[EvT], Protocol):

	def add_observer(self, observer: ObserverProtocol[EvT]): ...
	def rem_observer(self, observer: ObserverProtocol[EvT]): ...

class Herald(Generic[T]):

	def __init__(self):

		self._observers: list[ObserverProtocol[T]] = []

	def add_observer(self, observer: ObserverProtocol[T]):
		self._observers.append(observer)

	def rem_observer(self, observer: ObserverProtocol[T]):
		self._observers.remove(observer)

	def _dispatch_event(self, event: T):

		for observer in self._observers:
			observer.on_event(event)
