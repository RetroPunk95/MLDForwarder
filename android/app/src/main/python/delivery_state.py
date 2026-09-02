"""Journal de entregas: pendências não são confirmações de sincronização.

Um resultado incerto (conexão perdida/encerramento durante o envio) exige
conferência, em vez de uma repetição automática que poderia duplicar conteúdo.
"""

import hashlib
import json
from datetime import datetime, timezone


class DeliveryStopped(Exception):
    pass


class DeliveryNeedsReview(Exception):
    pass


class DeliveryStorageError(RuntimeError):
    pass


def route_key(route):
    return (
        f"{route['source']}:{route['source_topic'] or 0}"
        f"->{route['target']}:{route['target_topic'] or 0}"
    )


class DeliveryJournal:
    def __init__(self, path):
        self.path = path
        self.entries = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("version") != 1 or not isinstance(data.get("entries"), dict):
                    raise ValueError("formato desconhecido")
                self.entries = data["entries"]
                for key, entry in self.entries.items():
                    if (
                        not isinstance(entry, dict)
                        or entry.get("key") != key
                        or not isinstance(entry.get("attempts"), int)
                        or not isinstance(entry.get("split_caption"), bool)
                        or not isinstance(entry.get("ids"), list)
                        or not entry["ids"]
                        or not all(isinstance(i, int) and i > 0 for i in entry["ids"])
                        or not isinstance(entry.get("confirmed"), dict)
                        or not isinstance(entry.get("route"), dict)
                        or entry.get("route_key") != route_key(entry["route"])
                        or entry.get("kind") not in ("message", "album")
                        or entry.get("status") not in ("ready", "pending", "review", "sent")
                    ):
                        raise ValueError("registro inválido")
                    if entry.get("in_flight"):
                        entry["status"] = "review"
                        entry["error"] = "Aplicativo interrompido durante envio; conferir destino."
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
                raise DeliveryStorageError(
                    "Não foi possível ler as pendências; arquivo preservado. "
                    "Sincronização interrompida para evitar perdas."
                ) from error

    def save(self):
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps({"version": 1, "entries": self.entries}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as error:
            raise DeliveryStorageError("Falha ao salvar pendências; não é seguro continuar.") from error

    def begin(self, route, kind, messages):
        ids = [int(message.id) for message in messages]
        key = hashlib.sha256(
            json.dumps([route_key(route), kind, ids]).encode("utf-8")
        ).hexdigest()
        if key not in self.entries:
            self.entries[key] = {
                "key": key,
                "route_key": route_key(route),
                "route": dict(route),
                "kind": kind,
                "ids": ids,
                "status": "ready",
                "attempts": 0,
                "confirmed": {},
                "in_flight": None,
                "split_caption": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self.save()
        return self.entries[key]

    def update(self, entry, **values):
        entry.update(values)
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def ack(self, entry):
        # Apenas após o cursor ser salvo, ou após recuperar uma pendência antiga.
        if entry["status"] == "sent":
            self.entries.pop(entry["key"], None)
            self.save()

    def pending(self, route):
        return [
            entry for entry in list(self.entries.values())
            if entry["route_key"] == route_key(route) and entry["status"] != "sent"
        ]


class DeliveryContext:
    def __init__(self, journal, entry, stop, sleep, log):
        self.journal = journal
        self.entry = entry
        self.stop = stop
        self.sleep = sleep
        self.log = log

    async def operation(self, key, callback):
        if key in self.entry["confirmed"]:
            return
        if self.entry.get("in_flight") or self.entry["status"] == "review":
            raise DeliveryNeedsReview("Resultado de envio incerto; confira o destino antes de repetir.")
        while True:
            if self.stop():
                raise DeliveryStopped()
            self.journal.update(self.entry, in_flight=key)
            try:
                result = await callback()
            except Exception as error:
                # Uma rejeição RPC 4xx é explícita: nada foi aceito nessa operação.
                # Erros locais/de rede/5xx não dão a mesma garantia.
                from telethon.errors import RPCError, FloodWaitError
                if isinstance(error, RPCError) and 400 <= error.code < 500:
                    self.journal.update(self.entry, in_flight=None)
                    if isinstance(error, FloodWaitError):
                        self.log(f"FloodWait: aguardando {error.seconds} segundos.")
                        if not await self.sleep(error.seconds):
                            raise DeliveryStopped() from error
                        continue
                raise
            items = result if isinstance(result, (list, tuple)) else [result]
            self.entry["confirmed"][key] = [
                int(item.id) for item in items if getattr(item, "id", None)
            ]
            self.journal.update(self.entry, in_flight=None)
            return
