from contextvars import ContextVar

_tokens_used = ContextVar("tokens_used", default=None)


def start_request():
    _tokens_used.set({"total": 0})


def add_tokens(count: int):
    if count is None:
        return
    try:
        current = _tokens_used.get()
    except LookupError:
        current = None

    if not isinstance(current, dict):
        current = {"total": int(current or 0)}
        _tokens_used.set(current)

    current["total"] += max(0, int(count))


def get_tokens() -> int:
    try:
        current = _tokens_used.get()
        if isinstance(current, dict):
            return int(current.get("total", 0))
        return int(current or 0)
    except Exception:
        return 0
