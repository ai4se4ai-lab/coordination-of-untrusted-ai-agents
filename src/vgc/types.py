from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Binding:
    stage: str
    rank: int
    prerequisites: tuple[str, ...]
    owner: str
    contract: str = "v1"


@dataclass
class Record:
    episode: int
    signature: str
    attempts: int = 0
    failed: bool = False
    value: Any = None
    stamp: str | None = None
    evidence_owner: str | None = None
    evidence_request: str | None = None


@dataclass(frozen=True)
class Request:
    identity: str
    job: str
    episode: int
    attempt: int
    observation: str
    owner: str
