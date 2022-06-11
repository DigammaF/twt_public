
from typing import Protocol

from tag import SystemTag

class SystemProtocol(Protocol):

	tags: frozenset[SystemTag]
