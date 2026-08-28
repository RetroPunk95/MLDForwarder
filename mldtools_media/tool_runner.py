from __future__ import annotations

import os
import re
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .paths import APP_ROOT
from .process_control import terminate_process_tree
from .tdl_client import (
    TDLClient,
    friendly_tdl_error,
    is_database_in_use_error,
    strip_ansi,
)


PERCENT_RE = re.compile(r"(?<!\d)(100|\d{1,2})(?:\.\d+)?%")
SPEED_RE = re.compile(r"(\d+(?:\.\d+)?\s*(?:KiB|MiB|GiB|KB|MB|GB)/s)", re.I)
CANCEL_GRACE_SECONDS = 4.0


class ToolRunner:
    """Runs one export or upload job without blocking the Tk main loop."""

    def __init__(
        self,
        client: TDLClient,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.client = client
        self.event_callback = event_callback or (lambda _event: None)
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[str] | None = None
        self._stop_thread: threading.Thread | None = None
        self._cancel_signal_path: Path | None = None
        self._kind = ""
        self._cancelled = False

    @property
    def active_kind(self) -> str:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self._kind
            return ""

    def start(self, kind: str, label: str, command: list[str]) -> bool:
        command = list(command)
        config_path = self._album_config_path(command)
        cancel_signal = (
            config_path.with_suffix(config_path.suffix + ".cancel")
            if config_path is not None
            else None
        )
        if cancel_signal is not None:
            cancel_signal.unlink(missing_ok=True)
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            token = self.client.acquire_operation(label)
            self._kind = kind
            self._cancelled = False
            self._stop_thread = None
            self._cancel_signal_path = cancel_signal
            self._thread = threading.Thread(
                target=self._run,
                args=(kind, command, token, config_path, cancel_signal),
                name=f"mldtools-{kind}",
                daemon=True,
            )
            try:
                self._thread.start()
            except Exception:
                self.client.release_operation(token)
                self._thread = None
                self._kind = ""
                raise
        return True

    def cancel(self) -> bool:
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return False
            self._cancelled = True
            process = self._process
            cancel_signal = self._cancel_signal_path
        cooperative = False
        if cancel_signal is not None:
            try:
                cancel_signal.touch(exist_ok=True)
                cooperative = True
            except OSError:
                cooperative = False
        if process is not None and process.poll() is None:
            self._schedule_process_stop(process, cooperative=cooperative)
        return True

    def shutdown(self) -> None:
        self.cancel()
        with self._lock:
            thread = self._thread
            stop_thread = self._stop_thread
        if stop_thread and stop_thread.is_alive():
            stop_thread.join(timeout=CANCEL_GRACE_SECONDS + 2)
        if thread and thread.is_alive():
            thread.join(timeout=3)
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            self._terminate_process_tree(process)
        if thread and thread.is_alive():
            thread.join(timeout=2)

    @staticmethod
    def _album_config_path(command: list[str]) -> Path | None:
        try:
            index = command.index("--config")
            path = Path(command[index + 1]).expanduser()
        except (ValueError, IndexError):
            return None
        if path.name.startswith("album-upload-") and path.suffix.casefold() == ".json":
            return path
        return None

    def _schedule_process_stop(
        self,
        process: subprocess.Popen[str],
        *,
        cooperative: bool,
    ) -> None:
        with self._lock:
            if self._stop_thread and self._stop_thread.is_alive():
                return
            self._stop_thread = threading.Thread(
                target=self._stop_process,
                args=(process, cooperative),
                name="mldtools-cancel-tool",
                daemon=True,
            )
            self._stop_thread.start()

    def _stop_process(self, process: subprocess.Popen[str], cooperative: bool) -> None:
        if cooperative:
            try:
                process.wait(timeout=CANCEL_GRACE_SECONDS)
                return
            except subprocess.TimeoutExpired:
                pass
        self._terminate_process_tree(process)

    @staticmethod
    def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
        terminate_process_tree(process)

    def _emit(self, event_type: str, **data: Any) -> None:
        try:
            self.event_callback({"type": event_type, **data})
        except Exception:
            pass

    def _run(
        self,
        kind: str,
        command: list[str],
        token: object,
        config_path: Path | None,
        cancel_signal: Path | None,
    ) -> None:
        output_tail: list[str] = []
        code = 1
        failure_message = ""
        process: subprocess.Popen[str] | None = None
        try:
            if not self.client.engine_exists():
                raise FileNotFoundError(f"Motor tdl não encontrado em {self.client.executable}")
            creationflags = 0
            if os.name == "nt":
                creationflags = (
                    subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            environment = os.environ.copy()
            environment.setdefault("NO_COLOR", "1")
            environment["PYTHONUTF8"] = "1"
            environment["PYTHONIOENCODING"] = "utf-8"
            process = subprocess.Popen(
                command,
                cwd=APP_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                env=environment,
                start_new_session=os.name != "nt",
            )
            with self._lock:
                self._process = process
                cancel_requested = self._cancelled
            if cancel_requested:
                self._schedule_process_stop(
                    process,
                    cooperative=cancel_signal is not None and cancel_signal.exists(),
                )
            self._emit("tool_started", kind=kind)
            assert process.stdout is not None
            for raw_line in iter(process.stdout.readline, ""):
                line = strip_ansi(raw_line)
                if not line:
                    continue
                output_tail.append(line)
                del output_tail[:-20]
                self._emit("tool_log", kind=kind, message=line)
                percents = PERCENT_RE.findall(line)
                speeds = SPEED_RE.findall(line)
                if percents or speeds:
                    self._emit(
                        "tool_progress",
                        kind=kind,
                        progress=float(percents[-1]) if percents else None,
                        speed=speeds[-1] if speeds else "",
                    )
            code = process.wait()
            process.stdout.close()
        except Exception as exc:
            failure_message = str(exc)
        finally:
            self.client.release_operation(token)
            if process is not None and process.stdout is not None:
                process.stdout.close()
            if config_path is not None:
                config_path.unlink(missing_ok=True)
            if cancel_signal is not None:
                cancel_signal.unlink(missing_ok=True)
            with self._lock:
                cancelled = self._cancelled
                self._process = None
                self._cancel_signal_path = None

        if cancelled:
            self._emit("tool_cancelled", kind=kind)
        elif failure_message:
            self._emit("tool_failed", kind=kind, message=failure_message)
        elif code == 0:
            self._emit("tool_finished", kind=kind)
        else:
            output = "\n".join(output_tail)
            message = (
                friendly_tdl_error(output)
                if is_database_in_use_error(output)
                else (output[-1200:] or f"O tdl encerrou com o código {code}.")
            )
            self._emit("tool_failed", kind=kind, message=message)
