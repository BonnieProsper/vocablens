from contextvars import ContextVar

_tokens_used = ContextVar("tokens_used", default=0)


def start_request():
    _tokens_used.set(0)


def add_tokens(count: int):
    if count is None:
        return
    try:
        current = _tokens_used.get()
    except LookupError:
        current = 0
    _tokens_used.set(current + max(0, int(count)))


def get_tokens() -> int:
    try:
        return int(_tokens_used.get())
    except Exception:
        return 0
