import json
import os
import time

SERVICE_NAME = os.getenv("SERVICE_NAME", "unknown")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}

def _allowed(level: str) -> bool:
    return _LEVELS.get(level, 20) >= _LEVELS.get(LOG_LEVEL, 20)

def log(level: str, event: str, *, correlation_id=None, aws_request_id=None, **fields):
    if not _allowed(level):
        return

    payload = {
        "ts": int(time.time() * 1000),
        "level": level,
        "service": SERVICE_NAME,
        "event": event,
        "correlation_id": correlation_id,
        "aws_request_id": aws_request_id,
        **fields,
    }
    print(json.dumps(payload, default=str))
