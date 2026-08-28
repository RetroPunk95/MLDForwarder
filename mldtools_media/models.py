from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class DownloadTask:
    title: str
    source_type: str
    source: dict[str, Any]
    destination: str
    options: dict[str, Any]
    operation_type: str = "download"
    id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "queued"
    progress: float = 0.0
    phase: str = "Aguardando"
    speed: str = ""
    estimated_bytes: int = 0
    error: str = ""
    resume_mode: bool = False
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadTask":
        allowed = cls.__dataclass_fields__.keys()
        clean = {key: value for key, value in data.items() if key in allowed}
        return cls(**clean)
