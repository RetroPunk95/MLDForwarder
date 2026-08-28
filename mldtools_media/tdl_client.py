from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .config_store import ConfigStore
from .models import DownloadTask
from .paths import APP_ROOT, DATA_DIR, TASK_WORK_DIR, tdl_executable


ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
DATABASE_IN_USE_TEXT = "current database is used by another process"
ORIGINAL_FILENAME_TEMPLATE = "{{ filenamify .FileName }}"
ALBUM_MAX_PARALLEL_UPLOADS = 4


class EngineBusyError(RuntimeError):
    """Raised when another MLD Tools operation is already using tdl."""

    def __init__(self, active_operation: str = "outra operação") -> None:
        super().__init__(
            f"O motor do Telegram já está ocupado com {active_operation}. "
            "Aguarde a operação terminar e tente novamente."
        )


def friendly_tdl_error(value: str) -> str:
    message = strip_ansi(value)
    if is_database_in_use_error(message):
        return (
            "O banco local do Telegram está aberto por outro processo tdl.\n\n"
            "Feche todas as janelas de autenticação do MLD Tools e encerre qualquer "
            "tdl.exe restante no Gerenciador de Tarefas. Depois, abra o MLD Tools e "
            "tente novamente. Se o erro persistir mesmo sem tdl.exe em execução, "
            "reinicie o Windows uma vez."
        )
    return message


def is_database_in_use_error(value: str) -> bool:
    return DATABASE_IN_USE_TEXT in strip_ansi(value).casefold()


def strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value).replace("\x00", "").strip()


def extract_json(value: str) -> Any:
    clean = ANSI_RE.sub("", value)
    decoder = json.JSONDecoder()
    for index, char in enumerate(clean):
        if char not in "[{":
            continue
        try:
            result, _ = decoder.raw_decode(clean[index:])
            return result
        except json.JSONDecodeError:
            continue
    raise ValueError("A saída do tdl não contém JSON válido")


def _normalised_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _dict_value(mapping: dict[str, Any], *names: str, default: Any = None) -> Any:
    normalised = {_normalised_key(key): value for key, value in mapping.items()}
    for name in names:
        key = _normalised_key(name)
        if key in normalised:
            return normalised[key]
    return default


def normalise_extensions(value: Any) -> str:
    pieces = re.split(r"[,;\s]+", str(value).strip())
    return ",".join(piece.lstrip(".") for piece in pieces if piece.lstrip("."))


def normalise_chat_rows(payload: Any) -> list[dict[str, Any]]:
    rows: Any = payload
    if isinstance(payload, dict):
        for key in ("chats", "dialogs", "data", "items", "result"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    if not isinstance(rows, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        chat_id = _dict_value(raw, "id", "chat_id", default="")
        visible_name = _dict_value(
            raw,
            "visible_name",
            "name",
            "title",
            default="",
        )
        username = _dict_value(raw, "username", "user_name", default="")
        if not str(visible_name).strip():
            visible_name = f"@{str(username).lstrip('@')}" if str(username).strip("@ ") else chat_id
        chat_type = _dict_value(raw, "type", "chat_type", default="chat")
        topics_raw = _dict_value(raw, "topics", default=[])
        topics: list[dict[str, Any]] = []
        if isinstance(topics_raw, list):
            for topic in topics_raw:
                if not isinstance(topic, dict):
                    continue
                topic_id = _dict_value(topic, "id", "topic_id", default="")
                topic_name = _dict_value(topic, "title", "name", default=topic_id)
                topics.append({"id": str(topic_id), "name": str(topic_name)})
        result.append(
            {
                "id": str(chat_id),
                "name": str(visible_name),
                "username": str(username),
                "type": str(chat_type),
                "topics": topics,
                "raw": raw,
            }
        )
    return result


def estimate_media_bytes(payload: Any) -> int:
    """Best-effort size estimate for tdl and Telegram Desktop exports.

    Both formats have changed field casing over time. Count at most one direct
    size field per dictionary and then recurse into child objects. This avoids
    counting aliases such as ``Size`` and ``FileSize`` twice.
    """

    size_keys = {"size", "filesize", "file_size", "media_size"}

    def walk(value: Any) -> int:
        if isinstance(value, list):
            return sum(walk(item) for item in value)
        if not isinstance(value, dict):
            return 0
        own_size = 0
        own_key = ""
        for key, child in value.items():
            normalised = str(key).replace("-", "_").casefold()
            if normalised not in size_keys or isinstance(child, bool):
                continue
            try:
                candidate = int(child)
            except (TypeError, ValueError):
                continue
            if candidate > 0:
                own_size = candidate
                own_key = str(key)
                break
        nested = sum(
            walk(child)
            for key, child in value.items()
            if key != own_key and isinstance(child, (dict, list))
        )
        return own_size + nested

    return walk(payload)


class TDLClient:
    def __init__(self, config: ConfigStore):
        self.config = config
        self._operation_lock = threading.Lock()
        self._operation_meta_lock = threading.Lock()
        self._active_operation = ""
        self._active_operation_token: object | None = None

    @property
    def active_operation(self) -> str:
        with self._operation_meta_lock:
            return self._active_operation

    def acquire_operation(self, label: str) -> object:
        token = object()
        if not self._operation_lock.acquire(blocking=False):
            raise EngineBusyError(self.active_operation or "outra operação")
        with self._operation_meta_lock:
            self._active_operation = label
            self._active_operation_token = token
        return token

    def release_operation(self, token: object) -> bool:
        with self._operation_meta_lock:
            if token is not self._active_operation_token:
                return False
            self._operation_lock.release()
            self._active_operation = ""
            self._active_operation_token = None
        return True

    @contextmanager
    def operation(self, label: str) -> Iterator[None]:
        token = self.acquire_operation(label)
        try:
            yield
        finally:
            self.release_operation(token)

    @property
    def executable(self) -> Path:
        return tdl_executable()

    def engine_exists(self) -> bool:
        path = self.executable
        if path.is_absolute() or path.parent != Path("."):
            return path.exists()
        return shutil.which(str(path)) is not None

    def session_exists(self) -> bool:
        storage = DATA_DIR / "tdl"
        if not storage.exists():
            return False
        return any(path.is_file() and path.stat().st_size > 0 for path in storage.rglob("*"))

    def _global_args(self) -> list[str]:
        cfg = self.config.get_all()
        storage = DATA_DIR / "tdl"
        args = [
            str(self.executable),
            "-n",
            cfg["namespace"],
            "--storage",
            f"type=bolt,path={storage}",
            "--disable-progress-ps",
            "--pool",
            str(cfg["dc_pool"]),
            "--reconnect-timeout",
            cfg["reconnect_timeout"],
        ]
        if cfg["proxy"]:
            args.extend(["--proxy", cfg["proxy"]])
        if cfg["delay_seconds"]:
            args.extend(["--delay", f"{cfg['delay_seconds']}s"])
        return args

    def build_login_command(self, mode: str) -> list[str]:
        args = self._global_args() + ["login"]
        if mode == "qr":
            args.extend(["-T", "qr"])
        elif mode == "code":
            args.extend(["-T", "code"])
        elif mode != "desktop":
            raise ValueError("Modo de login desconhecido")
        return args

    def build_chat_list_command(self) -> list[str]:
        return self._global_args() + ["chat", "ls", "-o", "json"]

    def build_export_command(self, task: DownloadTask, output_file: Path) -> list[str]:
        source = task.source
        return self.build_message_export_command(
            chat_id=str(source.get("chat_id", "")),
            output_file=output_file,
            topic_id=str(source.get("topic_id", "")),
            scope=str(source.get("scope", "all")),
            scope_value=str(source.get("scope_value", "")),
        )

    @staticmethod
    def _append_export_scope(args: list[str], scope: str, scope_value: str) -> None:
        scope = str(scope).strip().casefold()
        scope_value = str(scope_value).strip()
        if scope == "last":
            count = int(scope_value)
            if count < 1:
                raise ValueError("A quantidade deve ser maior que zero")
            args.extend(["-T", "last", "-i", str(count)])
        elif scope == "id":
            if not re.fullmatch(r"\d+\s*,\s*\d+", scope_value):
                raise ValueError("Use o intervalo de IDs no formato início,fim")
            args.extend(["-T", "id", "-i", re.sub(r"\s+", "", scope_value)])
        elif scope == "time":
            values = [piece.strip() for piece in scope_value.split(",")]
            if len(values) != 2:
                raise ValueError("Use duas datas no formato AAAA-MM-DD,AAAA-MM-DD")
            timestamps = []
            for index, value in enumerate(values):
                moment = datetime.strptime(value, "%Y-%m-%d")
                if index == 1:
                    moment = moment.replace(hour=23, minute=59, second=59)
                timestamps.append(str(int(moment.timestamp())))
            args.extend(["-T", "time", "-i", ",".join(timestamps)])
        elif scope != "all":
            raise ValueError("Escopo de canal desconhecido")

    def build_message_export_command(
        self,
        chat_id: str,
        output_file: str | Path,
        *,
        topic_id: str = "",
        scope: str = "all",
        scope_value: str = "",
        include_non_media: bool = False,
        with_content: bool = False,
        raw: bool = False,
        filter_expression: str = "",
    ) -> list[str]:
        chat_id = str(chat_id).strip()
        if not chat_id:
            raise ValueError("Canal ou grupo não informado")
        output = Path(output_file).expanduser()
        if output.suffix.casefold() != ".json":
            raise ValueError("O arquivo de exportação deve usar a extensão .json")
        args = self._global_args() + [
            "chat",
            "export",
            "-c",
            chat_id,
            "-o",
            str(output),
        ]
        topic_id = str(topic_id).strip()
        if topic_id:
            args.extend(["--topic", topic_id])
        self._append_export_scope(args, scope, scope_value)
        if include_non_media:
            args.append("--all")
        if with_content:
            args.append("--with-content")
        if raw:
            args.append("--raw")
        filter_expression = str(filter_expression).strip()
        if filter_expression:
            args.extend(["-f", filter_expression])
        return args

    def build_user_export_command(
        self,
        chat_id: str,
        output_file: str | Path,
        *,
        raw: bool = False,
    ) -> list[str]:
        chat_id = str(chat_id).strip()
        if not chat_id:
            raise ValueError("Canal ou grupo não informado")
        output = Path(output_file).expanduser()
        if output.suffix.casefold() != ".json":
            raise ValueError("O arquivo de exportação deve usar a extensão .json")
        args = self._global_args() + [
            "chat",
            "users",
            "-c",
            chat_id,
            "-o",
            str(output),
        ]
        if raw:
            args.append("--raw")
        return args

    @staticmethod
    def _validated_upload_paths(paths: Iterable[str | Path]) -> list[Path]:
        filenames = [Path(path).expanduser() for path in paths]
        if not filenames:
            raise ValueError("Selecione pelo menos um arquivo ou pasta")
        missing = [str(path) for path in filenames if not path.exists()]
        if missing:
            raise ValueError(f"Arquivo ou pasta não encontrado: {missing[0]}")
        return filenames

    @staticmethod
    def _validated_upload_filters(
        include_extensions: str,
        exclude_extensions: str,
    ) -> tuple[str, str]:
        include = normalise_extensions(include_extensions)
        exclude = normalise_extensions(exclude_extensions)
        if include and exclude:
            raise ValueError("Use somente a lista de incluir ou a lista de excluir extensões")
        return include, exclude

    def build_upload_command(
        self,
        paths: Iterable[str | Path],
        *,
        chat_id: str = "",
        topic_id: str = "",
        caption: str = "",
        as_photo: bool = False,
        include_extensions: str = "",
        exclude_extensions: str = "",
    ) -> list[str]:
        filenames = self._validated_upload_paths(paths)

        args = self._global_args() + ["upload"]
        cfg = self.config.get_all()
        args.extend(["-t", str(cfg["threads_per_file"])])
        args.extend(["-l", str(cfg["parallel_downloads"])])
        for filename in filenames:
            args.extend(["-p", str(filename)])

        chat_id = str(chat_id).strip()
        topic_id = str(topic_id).strip()
        if chat_id:
            args.extend(["-c", chat_id])
        if topic_id:
            if not chat_id:
                raise ValueError("Um tópico exige a seleção de um grupo de destino")
            args.extend(["--topic", topic_id])

        # tdl captions are expressions. JSON encoding produces a safe literal
        # string, including quotes, accents and line breaks entered in the UI.
        args.extend(["--caption", json.dumps(str(caption), ensure_ascii=False)])
        include, exclude = self._validated_upload_filters(
            include_extensions,
            exclude_extensions,
        )
        if include:
            args.extend(["-i", include])
        if exclude:
            args.extend(["-e", exclude])
        if as_photo:
            args.append("--photo")
        return args

    def build_album_upload_command(
        self,
        paths: Iterable[str | Path],
        *,
        chat_id: str = "",
        chat_type: str = "",
        chat_username: str = "",
        topic_id: str = "",
        caption: str = "",
        as_photo: bool = False,
        include_extensions: str = "",
        exclude_extensions: str = "",
        album_mode: str = "selection",
    ) -> list[str]:
        filenames = self._validated_upload_paths(paths)
        if album_mode not in {"selection", "folder"}:
            raise ValueError("Modo de agrupamento de álbum desconhecido")
        if topic_id and not chat_id:
            raise ValueError("Um tópico exige a seleção de um grupo de destino")
        self._validated_upload_filters(include_extensions, exclude_extensions)

        TASK_WORK_DIR.mkdir(parents=True, exist_ok=True)
        cfg = self.config.get_all()
        payload = {
            "paths": [str(path) for path in filenames],
            "chat_id": str(chat_id).strip(),
            "chat_type": str(chat_type).strip(),
            "chat_username": str(chat_username).strip(),
            "topic_id": str(topic_id).strip(),
            "caption": str(caption),
            "as_photo": bool(as_photo),
            "include_extensions": str(include_extensions),
            "exclude_extensions": str(exclude_extensions),
            "album_mode": album_mode,
            "parallel_uploads": max(
                1,
                min(
                    int(cfg["parallel_downloads"]),
                    ALBUM_MAX_PARALLEL_UPLOADS,
                ),
            ),
        }
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix="album-upload-",
            dir=TASK_WORK_DIR,
            delete=False,
        ) as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            config_path = Path(stream.name)

        if getattr(sys, "frozen", False):
            worker = APP_ROOT / "MLDToolsAlbum.exe"
            if not worker.exists():
                config_path.unlink(missing_ok=True)
                raise FileNotFoundError(
                    "MLDToolsAlbum.exe não foi encontrado na pasta do MLD Tools"
                )
            return [str(worker), "--config", str(config_path)]
        return [
            sys.executable,
            "-u",
            str(APP_ROOT / "album_uploader.py"),
            "--config",
            str(config_path),
        ]

    def validate_upload_task(self, task: DownloadTask) -> None:
        if task.operation_type != "upload" or task.source_type != "upload":
            raise ValueError("A tarefa não é um upload")
        source = task.source
        options = task.options
        if "chat_id" not in source:
            raise ValueError(
                "Este registro de upload é de uma versão anterior. "
                "Abra a tela de upload e selecione novamente o destino."
            )
        paths = source.get("paths", [])
        if not isinstance(paths, list):
            raise ValueError("A lista de arquivos do upload é inválida")
        self._validated_upload_paths(paths)
        chat_id = str(source.get("chat_id", "")).strip()
        topic_id = str(source.get("topic_id", "")).strip()
        if topic_id and not chat_id:
            raise ValueError("Um tópico exige a seleção de um grupo de destino")
        self._validated_upload_filters(
            str(options.get("include_extensions", "")),
            str(options.get("exclude_extensions", "")),
        )
        if options.get("group_albums", False) and str(
            options.get("album_mode", "selection")
        ) not in {"selection", "folder"}:
            raise ValueError("Modo de agrupamento de álbum desconhecido")

    def build_upload_task_command(self, task: DownloadTask) -> list[str]:
        self.validate_upload_task(task)
        source = task.source
        options = task.options
        common = {
            "chat_id": str(source.get("chat_id", "")),
            "topic_id": str(source.get("topic_id", "")),
            "caption": str(options.get("caption", "")),
            "as_photo": bool(options.get("as_photo", False)),
            "include_extensions": str(options.get("include_extensions", "")),
            "exclude_extensions": str(options.get("exclude_extensions", "")),
        }
        paths = source.get("paths", [])
        if options.get("group_albums", False):
            return self.build_album_upload_command(
                paths,
                chat_type=str(source.get("chat_type", "")),
                chat_username=str(source.get("chat_username", "")),
                album_mode=str(options.get("album_mode", "selection")),
                **common,
            )
        return self.build_upload_command(paths, **common)

    def build_download_command(
        self,
        task: DownloadTask,
        exported_json: Path | None = None,
        resume: bool | None = None,
    ) -> list[str]:
        args = self._global_args() + ["dl"]
        source = task.source
        if task.source_type == "links":
            links = source.get("links", [])
            if not isinstance(links, list) or not links:
                raise ValueError("Nenhum link foi informado")
            for link in links:
                args.extend(["-u", str(link)])
        elif task.source_type == "json":
            files = source.get("files", [])
            if not isinstance(files, list) or not files:
                raise ValueError("Nenhum arquivo JSON foi informado")
            for filename in files:
                args.extend(["-f", str(filename)])
        elif task.source_type == "chat":
            if exported_json is None:
                raise ValueError("A exportação do canal ainda não foi criada")
            args.extend(["-f", str(exported_json)])
        else:
            raise ValueError("Tipo de origem desconhecido")

        options = task.options
        args.extend(["-d", task.destination])
        args.extend(["-t", str(int(options.get("threads_per_file", 8)))])
        args.extend(["-l", str(int(options.get("parallel_downloads", 4)))])
        if options.get("group_albums", True):
            args.append("--group")
        if options.get("skip_same", True):
            args.append("--skip-same")
        if options.get("takeout", False):
            args.append("--takeout")
        if options.get("descending", False):
            args.append("--desc")
        if options.get("rewrite_extension", False):
            args.append("--rewrite-ext")
        include = normalise_extensions(options.get("include_extensions", ""))
        exclude = normalise_extensions(options.get("exclude_extensions", ""))
        if include and exclude:
            raise ValueError("Use somente a lista de incluir ou a lista de excluir extensões")
        if include:
            args.extend(["-i", include])
        if exclude:
            args.extend(["-e", exclude])
        template = (
            ORIGINAL_FILENAME_TEMPLATE
            if options.get("keep_original_filename", False)
            else str(options.get("filename_template", "")).strip()
        )
        if template:
            args.extend(["--template", template])
        should_resume = task.resume_mode if resume is None else resume
        if should_resume:
            args.append("--continue")
        return args

    def task_export_path(self, task: DownloadTask) -> Path:
        workspace = Path(self.config.get("workspace_dir", str(TASK_WORK_DIR))).expanduser()
        directory = workspace / task.id
        directory.mkdir(parents=True, exist_ok=True)
        return directory / "messages.json"

    def launch_login(self, mode: str) -> tuple[subprocess.Popen[Any], object]:
        if not self.engine_exists():
            raise FileNotFoundError(f"Motor tdl não encontrado em {self.executable}")
        token = self.acquire_operation("a autenticação do Telegram")
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_CONSOLE
        try:
            process = subprocess.Popen(
                self.build_login_command(mode),
                cwd=APP_ROOT,
                creationflags=creationflags,
            )
        except Exception:
            self.release_operation(token)
            raise
        return process, token

    def run_chat_list(self, timeout: int = 120) -> list[dict[str, Any]]:
        if not self.engine_exists():
            raise FileNotFoundError(f"Motor tdl não encontrado em {self.executable}")
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with self.operation("a verificação da conta"):
            completed = subprocess.run(
                self.build_chat_list_command(),
                cwd=APP_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=creationflags,
                check=False,
            )
        if completed.returncode != 0:
            message = strip_ansi(completed.stdout) or f"tdl encerrou com código {completed.returncode}"
            raise RuntimeError(friendly_tdl_error(message[-1200:]))
        return normalise_chat_rows(extract_json(completed.stdout))

    def estimate_json_files(self, filenames: Iterable[str | Path]) -> int:
        total = 0
        for filename in filenames:
            path = Path(filename).expanduser()
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            total += estimate_media_bytes(payload)
        return total
