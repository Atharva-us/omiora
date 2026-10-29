"""Structured JSON logging with key-based redaction.

Never log request bodies, cookies, passwords, tokens, or provider credentials. Redaction is a
safety net, not a licence to pass sensitive values to the logger.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

SENSITIVE_KEY = re.compile(r"pass(word)?|secret|token|authorization|cookie|api[-_]?key|credential|session", re.I)
# Provider key shapes, in case one is interpolated into a message by mistake.
SECRET_VALUE = re.compile(r"sk-ant-[A-Za-z0-9_\-]+|sk-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}")
REDACTED = "[redacted]"

_RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


def redact(value: Any, key: str | None = None, depth: int = 0) -> Any:
    if key is not None and SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, dict) and depth < 4:
        return {k: redact(v, str(k), depth + 1) for k, v in value.items()}
    if isinstance(value, list | tuple) and depth < 4:
        return [redact(v, None, depth + 1) for v in value]
    if isinstance(value, str):
        return SECRET_VALUE.sub(REDACTED, value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "at": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": SECRET_VALUE.sub(REDACTED, record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = redact(value, key)
        if record.exc_info:
            payload["exception"] = SECRET_VALUE.sub(REDACTED, self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # The SDK's own debug logging can include request details; keep it quiet.
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("groq").setLevel(logging.WARNING)
