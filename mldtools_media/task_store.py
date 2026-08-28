from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Iterable

from .config_store import _atomic_json_write
from .models import DownloadTask, utc_now
from .paths import TASKS_FILE


class TaskStore:
    def __init__(self, path: Path = TASKS_FILE):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._normalised_on_load = False
        self._tasks: list[DownloadTask] = self._load()
        if self._normalised_on_load:
            self._save()

    def _load(self) -> list[DownloadTask]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        rows = raw.get("tasks", []) if isinstance(raw, dict) else raw
        tasks: list[DownloadTask] = []
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                try:
                    task = DownloadTask.from_dict(row)
                except (TypeError, ValueError):
                    continue
                if task.status == "running":
                    normalised_at = utc_now()
                    task.status = "paused"
                    if task.operation_type == "upload" and "chat_id" not in task.source:
                        task.status = "cancelled"
                        task.phase = "Upload antigo interrompido; selecione novamente o destino"
                        task.finished_at = normalised_at
                        task.resume_mode = False
                    elif task.operation_type == "upload":
                        task.phase = "Interrompido; o upload reiniciará do começo"
                        task.resume_mode = False
                    else:
                        task.phase = "Interrompido ao fechar o aplicativo"
                        task.resume_mode = True
                    task.updated_at = normalised_at
                    self._normalised_on_load = True
                tasks.append(task)
        return tasks

    def _save(self) -> None:
        _atomic_json_write(
            self.path,
            {"version": 2, "tasks": [task.to_dict() for task in self._tasks]},
        )

    def list(self) -> list[DownloadTask]:
        with self._lock:
            return [DownloadTask.from_dict(task.to_dict()) for task in self._tasks]

    def get(self, task_id: str) -> DownloadTask | None:
        with self._lock:
            for task in self._tasks:
                if task.id == task_id:
                    return DownloadTask.from_dict(task.to_dict())
        return None

    def add(self, task: DownloadTask) -> DownloadTask:
        with self._lock:
            if any(item.id == task.id for item in self._tasks):
                raise ValueError(f"A tarefa {task.id} já existe")
            self._tasks.append(task)
            self._save()
            return DownloadTask.from_dict(task.to_dict())

    def update(self, task_id: str, **changes: Any) -> DownloadTask | None:
        with self._lock:
            for task in self._tasks:
                if task.id != task_id:
                    continue
                for key, value in changes.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                task.updated_at = utc_now()
                self._save()
                return DownloadTask.from_dict(task.to_dict())
        return None

    def next_queued(self) -> DownloadTask | None:
        with self._lock:
            for task in self._tasks:
                if task.status == "queued":
                    return DownloadTask.from_dict(task.to_dict())
        return None

    def remove_finished(self, statuses: Iterable[str] = ("completed", "cancelled")) -> int:
        allowed = set(statuses)
        with self._lock:
            before = len(self._tasks)
            self._tasks = [task for task in self._tasks if task.status not in allowed]
            removed = before - len(self._tasks)
            if removed:
                self._save()
            return removed
