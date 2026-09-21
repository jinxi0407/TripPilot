import json
import logging
from datetime import UTC, datetime


class SafeJSONFormatter(logging.Formatter):
    """Allowlisted metadata only: never serialize messages, exceptions, or upstream bodies."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "time": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "event": getattr(record, "event_code", "application_event"),
            }
        )


class NoQueryString(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) == 5:
            address, method, path, version, status = record.args
            record.args = (address, method, str(path).split("?", 1)[0], version, status)
        return True


def configure_logging() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, NoQueryString) for f in access.filters):
        access.addFilter(NoQueryString())
    handler = logging.StreamHandler()
    handler.setFormatter(SafeJSONFormatter())
    logger = logging.getLogger("trippilot")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # HTTP clients can otherwise log URLs containing Amap's query-string key.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
