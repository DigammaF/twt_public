
from typing import TypeVar, Generic, Any

SourceType = TypeVar("SourceType")
TargetType = TypeVar("TargetType")

class CasterFactory(Generic[SourceType, TargetType]):

	def __call__(self, obj: SourceType) -> TargetType:
		return obj # type: ignore

def cast(obj: Any, target_type: type[TargetType], /) -> TargetType:
	return obj # type: ignore
