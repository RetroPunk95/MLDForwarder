from __future__ import annotations

import os
import sys
from pathlib import Path


def application_root() -> Path:
    override = os.environ.get("MLDTOOLS_APP_ROOT") or os.environ.get("MLDFETCH_APP_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


APP_ROOT = application_root()
DATA_DIR = APP_ROOT / "data"
ENGINE_DIR = APP_ROOT / "engine"
LOG_DIR = DATA_DIR / "logs"
TASK_WORK_DIR = DATA_DIR / "tasks"
CONFIG_FILE = DATA_DIR / "config.json"
TASKS_FILE = DATA_DIR / "tasks.json"


def ensure_runtime_directories() -> None:
    for directory in (DATA_DIR, LOG_DIR, TASK_WORK_DIR, DATA_DIR / "tdl"):
        directory.mkdir(parents=True, exist_ok=True)


def default_download_directory() -> Path:
    downloads = Path.home() / "Downloads"
    return downloads if downloads.exists() else Path.home()


def tdl_executable() -> Path:
    override = os.environ.get("MLDTOOLS_TDL") or os.environ.get("MLDFETCH_TDL")
    if override:
        return Path(override).expanduser().resolve()
    filename = "tdl.exe" if os.name == "nt" else "tdl"
    bundled = ENGINE_DIR / filename
    if bundled.exists():
        return bundled
    # The distributed build is Windows-only, but this fallback helps tests and
    # developers who have tdl on PATH in another operating system.
    return Path(filename)
