from __future__ import annotations

import json
import os
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import CONFIG_FILE, TASK_WORK_DIR, default_download_directory


DEFAULT_CONFIG: dict[str, Any] = {
    "default_download_dir": str(default_download_directory()),
    "workspace_dir": str(TASK_WORK_DIR),
    "namespace": "default",
    "threads_per_file": 8,
    "parallel_downloads": 4,
    "dc_pool": 8,
    "delay_seconds": 0,
    "reconnect_timeout": "2m",
    "proxy": "",
    "skip_same": True,
    "group_albums": True,
    "keep_original_filename": False,
    "takeout": False,
    "descending": False,
    "rewrite_extension": False,
    "include_extensions": "",
    "exclude_extensions": "",
    "filename_template": "",
    "confirm_full_chat": True,
    "window_geometry": "",
    "window_maximized": False,
}

PERFORMANCE_PROFILES: dict[str, tuple[int, int, int]] = {
    "balanced": (8, 4, 8),
    "fast": (16, 6, 12),
    "aggressive": (24, 8, 16),
}


def _atomic_json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


class ConfigStore:
    def __init__(self, path: Path = CONFIG_FILE):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._config = self._load()

    def _load(self) -> dict[str, Any]:
        config = deepcopy(DEFAULT_CONFIG)
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    config.update(raw)
            except (OSError, json.JSONDecodeError):
                pass
        return self._normalise(config)

    @staticmethod
    def _normalise(config: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(DEFAULT_CONFIG)
        result.update(config)
        for key, minimum, maximum in (
            ("threads_per_file", 1, 32),
            ("parallel_downloads", 1, 16),
            ("dc_pool", 1, 32),
            ("delay_seconds", 0, 3600),
        ):
            try:
                value = int(result[key])
            except (TypeError, ValueError):
                value = int(DEFAULT_CONFIG[key])
            result[key] = max(minimum, min(maximum, value))
        for key in (
            "skip_same",
            "group_albums",
            "keep_original_filename",
            "takeout",
            "descending",
            "rewrite_extension",
            "confirm_full_chat",
            "window_maximized",
        ):
            result[key] = bool(result.get(key, DEFAULT_CONFIG[key]))
        for key in (
            "default_download_dir",
            "workspace_dir",
            "namespace",
            "reconnect_timeout",
            "proxy",
            "include_extensions",
            "exclude_extensions",
            "filename_template",
            "window_geometry",
        ):
            result[key] = str(result.get(key, DEFAULT_CONFIG[key])).strip()
        if not result["namespace"]:
            result["namespace"] = "default"
        return result

    def get_all(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._config)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return deepcopy(self._config.get(key, default))

    def update(self, changes: dict[str, Any], save: bool = True) -> dict[str, Any]:
        with self._lock:
            merged = deepcopy(self._config)
            merged.update(changes)
            self._config = self._normalise(merged)
            if save:
                _atomic_json_write(self.path, self._config)
            return deepcopy(self._config)

    def ensure_saved(self) -> None:
        with self._lock:
            _atomic_json_write(self.path, self._config)
