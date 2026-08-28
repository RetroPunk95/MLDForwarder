from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models import DownloadTask, utc_now
from .paths import APP_ROOT
from .process_control import terminate_process_tree
from .task_store import TaskStore
from .tdl_client import (
    EngineBusyError,
    TDLClient,
    friendly_tdl_error,
    is_database_in_use_error,
    strip_ansi,
)


PERCENT_RE = re.compile(r"(?<!\d)(100|\d{1,2})(?:\.\d+)?%")
SPEED_RE = re.compile(r"(\d+(?:\.\d+)?\s*(?:KiB|MiB|GiB|KB|MB|GB)/s)", re.I)
CANCEL_GRACE_SECONDS = 4.0


class DownloadRunner:
    def __init__(
        self,
        store: TaskStore,
        client: TDLClient,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.store = store
        self.client = client
        self.event_callback = event_callback or (lambda _event: None)
        self._wake = threading.Event()
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[str] | None = None
        self._stop_thread: threading.Thread | None = None
        self._cancel_signal_path: Path | None = None
        self._active_task_id: str | None = None
        self._requested_action: str | None = None
        self._queue_enabled = False
        self._lock = threading.RLock()

    @property
    def active_task_id(self) -> str | None:
        with self._lock:
            return self._active_task_id

    @property
    def queue_enabled(self) -> bool:
        with self._lock:
            return self._queue_enabled

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._shutdown.clear()
        self._thread = threading.Thread(target=self._worker, name="mldtools-runner", daemon=True)
        self._thread.start()

    def notify(self) -> None:
        self._wake.set()

    def start_queue(self) -> bool:
        if self.store.next_queued() is None:
            return False
        with self._lock:
            self._queue_enabled = True
        self._wake.set()
        self._emit("queue_state", running=True)
        return True

    def stop_queue(self) -> bool:
        with self._lock:
            was_enabled = self._queue_enabled
            self._queue_enabled = False
        self._emit("queue_state", running=False)
        return was_enabled

    def pause(self, task_id: str) -> bool:
        task = self.store.get(task_id)
        if not task:
            return False
        with self._lock:
            if task_id == self._active_task_id:
                self._requested_action = "pause"
                self._request_process_stop_locked()
                return True
        if task.status == "queued":
            upload = task.operation_type == "upload"
            self.store.update(
                task_id,
                status="paused",
                phase=(
                    "Pausado — o upload reiniciará do começo"
                    if upload
                    else "Pausado"
                ),
                resume_mode=not upload,
            )
            self._emit("tasks_changed", task_id=task_id)
            return True
        return False

    def cancel(self, task_id: str) -> bool:
        task = self.store.get(task_id)
        if not task:
            return False
        with self._lock:
            if task_id == self._active_task_id:
                self._requested_action = "cancel"
                self._request_process_stop_locked()
                return True
        if task.status in {"queued", "paused", "failed"}:
            self.store.update(task_id, status="cancelled", phase="Cancelado", finished_at=utc_now())
            self._emit("tasks_changed", task_id=task_id)
            return True
        return False

    def resume(self, task_id: str) -> bool:
        task = self.store.get(task_id)
        if (
            not task
            or task.status not in {"paused", "failed", "cancelled"}
        ):
            return False
        if task.operation_type == "upload":
            try:
                self.client.validate_upload_task(task)
            except (OSError, TypeError, ValueError):
                return False
        upload = task.operation_type == "upload"
        self.store.update(
            task_id,
            status="queued",
            phase="Aguardando reinício" if upload else "Aguardando retomada",
            error="",
            progress=0.0 if upload else task.progress,
            resume_mode=not upload,
            finished_at="",
        )
        self.notify()
        self._emit("tasks_changed", task_id=task_id)
        return True

    def retry(self, task_id: str, restart: bool = False) -> bool:
        task = self.store.get(task_id)
        if (
            not task
            or task.status not in {"failed", "cancelled", "paused"}
        ):
            return False
        if task.operation_type == "upload":
            try:
                self.client.validate_upload_task(task)
            except (OSError, TypeError, ValueError):
                return False
        upload = task.operation_type == "upload"
        self.store.update(
            task_id,
            status="queued",
            phase="Aguardando",
            error="",
            progress=0.0 if restart or upload else task.progress,
            resume_mode=False if upload else not restart,
            finished_at="",
        )
        self.notify()
        self._emit("tasks_changed", task_id=task_id)
        return True

    def shutdown(self) -> None:
        self._shutdown.set()
        self.stop_queue()
        self._wake.set()
        with self._lock:
            if self._process and self._process.poll() is None:
                self._requested_action = "pause"
                self._request_process_stop_locked()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            terminate_process_tree(process)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _request_process_stop_locked(self) -> None:
        process = self._process
        cancel_signal = self._cancel_signal_path
        cooperative = False
        if cancel_signal is not None:
            try:
                cancel_signal.touch(exist_ok=True)
                cooperative = True
            except OSError:
                cooperative = False
        if process is None or process.poll() is not None:
            return
        if self._stop_thread and self._stop_thread.is_alive():
            return
        self._stop_thread = threading.Thread(
            target=self._stop_process,
            args=(process, cooperative),
            name="mldtools-cancel-transfer",
            daemon=True,
        )
        self._stop_thread.start()

    def _stop_process(self, process: subprocess.Popen[str], cooperative: bool) -> None:
        try:
            if cooperative:
                try:
                    process.wait(timeout=CANCEL_GRACE_SECONDS)
                    return
                except subprocess.TimeoutExpired:
                    pass
            terminate_process_tree(process)
        finally:
            with self._lock:
                if self._stop_thread is threading.current_thread():
                    self._stop_thread = None

    def _emit(self, event_type: str, **data: Any) -> None:
        try:
            self.event_callback({"type": event_type, **data})
        except Exception:
            pass

    def _worker(self) -> None:
        while not self._shutdown.is_set():
            if not self.queue_enabled:
                self._wake.wait(timeout=1.0)
                self._wake.clear()
                continue
            task = self.store.next_queued()
            if task is None:
                self.stop_queue()
                self._wake.wait(timeout=1.0)
                self._wake.clear()
                continue
            try:
                operation = "upload" if task.operation_type == "upload" else "download"
                with self.client.operation(f'o {operation} "{task.title}"'):
                    self._execute_task(task)
            except EngineBusyError:
                # Login and account verification have priority. Keep the task
                # queued instead of turning a normal wait into a failed transfer.
                self._wake.wait(timeout=0.5)
                self._wake.clear()

    def _execute_task(self, task: DownloadTask) -> None:
        with self._lock:
            self._active_task_id = task.id
            self._requested_action = None
        self.store.update(task.id, status="running", phase="Preparando", error="")
        self._emit("tasks_changed", task_id=task.id)
        exported_json: Path | None = None
        try:
            if task.operation_type == "upload":
                self._execute_upload(task)
                return
            Path(task.destination).expanduser().mkdir(parents=True, exist_ok=True)
            if task.source_type == "chat":
                exported_json = self.client.task_export_path(task)
                # Export again on every attempt. A pause can interrupt the JSON
                # write, and reusing a partial export would silently omit media.
                exported_json.unlink(missing_ok=True)
                self.store.update(task.id, phase="Lendo mensagens", progress=1.0)
                export_command = self.client.build_export_command(task, exported_json)
                if self._run_process(task.id, export_command, progress_floor=1.0, progress_ceiling=5.0) != 0:
                    return
                self.store.update(task.id, phase="Baixando arquivos", progress=max(5.0, task.progress))
            else:
                self.store.update(task.id, phase="Baixando arquivos")
            fresh = self.store.get(task.id) or task
            if not fresh.resume_mode and fresh.source_type in {"chat", "json"}:
                self.store.update(task.id, phase="Verificando espaço em disco")
                source_files = (
                    [exported_json]
                    if fresh.source_type == "chat" and exported_json is not None
                    else fresh.source.get("files", [])
                )
                estimated = self.client.estimate_json_files(source_files)
                if estimated > 0:
                    free = shutil.disk_usage(Path(fresh.destination).expanduser()).free
                    self.store.update(task.id, estimated_bytes=estimated)
                    self._emit(
                        "estimate",
                        task_id=task.id,
                        estimated_bytes=estimated,
                        free_bytes=free,
                    )
                    if estimated > free:
                        raise RuntimeError(
                            "Espaço insuficiente no destino: "
                            f"a exportação indica {estimated / (1024 ** 3):.1f} GB, "
                            f"mas há {free / (1024 ** 3):.1f} GB livres."
                        )
                self.store.update(task.id, phase="Baixando arquivos")
            download_command = self.client.build_download_command(
                fresh,
                exported_json=exported_json,
                resume=fresh.resume_mode,
            )
            code = self._run_process(task.id, download_command, progress_floor=5.0 if exported_json else 0.0)
            if code == 0:
                self.store.update(
                    task.id,
                    status="completed",
                    phase="Concluído",
                    progress=100.0,
                    speed="",
                    error="",
                    resume_mode=False,
                    finished_at=utc_now(),
                )
                self._emit("log", level="success", message=f"[{task.title}] Download concluído.")
                self._emit("tasks_changed", task_id=task.id)
        except Exception as exc:
            with self._lock:
                requested_action = self._requested_action
            if requested_action == "pause" or self._shutdown.is_set():
                upload = task.operation_type == "upload"
                self.store.update(
                    task.id,
                    status="paused",
                    phase=(
                        "Pausado — o upload reiniciará do começo"
                        if upload
                        else "Pausado"
                    ),
                    speed="",
                    resume_mode=not upload,
                )
            elif requested_action == "cancel":
                self.store.update(
                    task.id,
                    status="cancelled",
                    phase="Cancelado",
                    speed="",
                    resume_mode=task.operation_type == "download",
                    finished_at=utc_now(),
                )
            else:
                self.store.update(
                    task.id,
                    status="failed",
                    phase="Falhou",
                    error=str(exc),
                    speed="",
                    resume_mode=task.operation_type == "download",
                    finished_at=utc_now(),
                )
                self._emit("log", level="error", message=f"[{task.title}] {exc}")
            self._emit("tasks_changed", task_id=task.id)
        finally:
            with self._lock:
                self._process = None
                self._cancel_signal_path = None
                self._active_task_id = None
                self._requested_action = None

    def _execute_upload(self, task: DownloadTask) -> None:
        self.store.update(task.id, phase="Enviando arquivos", progress=0.0)
        command = self.client.build_upload_task_command(task)
        code = self._run_process(task.id, command)
        if code != 0:
            return
        self.store.update(
            task.id,
            status="completed",
            phase="Concluído",
            progress=100.0,
            speed="",
            error="",
            resume_mode=False,
            finished_at=utc_now(),
        )
        self._emit("log", level="success", message=f"[{task.title}] Upload concluído.")
        self._emit("tasks_changed", task_id=task.id)

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

    def _run_process(
        self,
        task_id: str,
        command: list[str],
        progress_floor: float = 0.0,
        progress_ceiling: float = 100.0,
    ) -> int:
        config_path = self._album_config_path(command)
        if config_path is None and not self.client.engine_exists():
            raise FileNotFoundError(f"Motor tdl não encontrado em {self.client.executable}")
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        environment = os.environ.copy()
        environment.setdefault("NO_COLOR", "1")
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"
        task = self.store.get(task_id)
        upload = bool(task and task.operation_type == "upload")
        operation = "upload" if upload else "download"
        self._emit("log", level="info", message=f"Iniciando motor de {operation}…")
        cancel_signal = (
            config_path.with_suffix(config_path.suffix + ".cancel")
            if config_path is not None
            else None
        )
        if cancel_signal is not None:
            cancel_signal.unlink(missing_ok=True)
        process: subprocess.Popen[str] | None = None
        output_tail: list[str] = []
        code = 1
        try:
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
                self._cancel_signal_path = cancel_signal
                if self._requested_action or self._shutdown.is_set():
                    self._request_process_stop_locked()
            assert process.stdout is not None
            for raw_line in iter(process.stdout.readline, ""):
                line = strip_ansi(raw_line)
                if not line:
                    continue
                output_tail.append(line)
                del output_tail[:-20]
                self._emit("log", level="engine", message=line)
                percents = PERCENT_RE.findall(line)
                speeds = SPEED_RE.findall(line)
                changes: dict[str, Any] = {}
                if percents:
                    raw_percent = float(percents[-1])
                    scaled = progress_floor + (raw_percent / 100.0) * (
                        progress_ceiling - progress_floor
                    )
                    changes["progress"] = max(
                        progress_floor,
                        min(progress_ceiling, scaled),
                    )
                if speeds:
                    changes["speed"] = speeds[-1]
                if changes:
                    self.store.update(task_id, **changes)
                    self._emit("progress", task_id=task_id, **changes)
                if self._shutdown.is_set() and process.poll() is None:
                    with self._lock:
                        self._requested_action = "pause"
                        self._request_process_stop_locked()
            code = process.wait()
        except BaseException:
            if process is not None and process.poll() is None:
                terminate_process_tree(process)
            raise
        finally:
            if process is not None and process.stdout is not None:
                process.stdout.close()
            if config_path is not None:
                config_path.unlink(missing_ok=True)
            if cancel_signal is not None:
                cancel_signal.unlink(missing_ok=True)
            with self._lock:
                self._cancel_signal_path = None
        with self._lock:
            requested_action = self._requested_action
        if requested_action == "pause" or self._shutdown.is_set():
            self.store.update(
                task_id,
                status="paused",
                phase=(
                    "Pausado — o upload reiniciará do começo"
                    if upload
                    else "Pausado"
                ),
                speed="",
                resume_mode=not upload,
            )
            self._emit("tasks_changed", task_id=task_id)
            return code or 1
        if requested_action == "cancel":
            self.store.update(
                task_id,
                status="cancelled",
                phase="Cancelado",
                speed="",
                resume_mode=not upload,
                finished_at=utc_now(),
            )
            self._emit("tasks_changed", task_id=task_id)
            return code or 1
        if code != 0:
            current_task = self.store.get(task_id)
            if current_task and current_task.status == "running":
                engine_output = "\n".join(output_tail)
                if is_database_in_use_error(engine_output):
                    error = friendly_tdl_error(engine_output)
                elif upload:
                    error = engine_output[-1200:] or (
                        f"O motor de upload encerrou com o código {code}."
                    )
                else:
                    error = f"O tdl encerrou com o código {code}. Consulte o log."
                self.store.update(
                    task_id,
                    status="failed",
                    phase="Falhou",
                    speed="",
                    error=error,
                    resume_mode=not upload,
                    finished_at=utc_now(),
                )
                self._emit(
                    "log",
                    level="error",
                    message=f"[{current_task.title}] {error}",
                )
                self._emit("tasks_changed", task_id=task_id)
        return code
