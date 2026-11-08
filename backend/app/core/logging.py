"""JSON logs with request_id (TZ 15). Never log keys or full user text beyond a short preview."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_data", None)
        if extra:
            data.update(extra)
        return json.dumps(data, ensure_ascii=False)


def setup_logging() -> None:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [h]
    root.setLevel(logging.INFO)


def log_event(logger: logging.Logger, msg: str, **data) -> None:
    logger.info(msg, extra={"extra_data": data})
