import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
            "endpoint": getattr(record, "endpoint", None),
            "latency": getattr(record, "latency", None),
            "error": getattr(record, "error", None),
            "extra": {},
        }
        for key, value in record.__dict__.items():
            if key in payload or key.startswith("_") or key in ("msg", "args", "levelno", "levelname", "created"):
                continue
            payload["extra"][key] = value
        return json.dumps(payload, default=str)


def setup_logging(level: int = logging.INFO):
    handler = logging.StreamHandler(sys.stdout)
    formatter = JSONFormatter()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str):
    return logging.getLogger(name)
