import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    SECRET_KEY: str = os.getenv("VOCABLENS_SECRET", "dev-secret-change-me")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost/vocablens",
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "15"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    TRANSLATE_TIMEOUT: float = float(os.getenv("TRANSLATE_TIMEOUT", "10"))

    ENABLE_BACKGROUND_TASKS: bool = _as_bool(os.getenv("ENABLE_BACKGROUND_TASKS"), False)
    ENABLE_REDIS_CACHE: bool = _as_bool(os.getenv("ENABLE_REDIS_CACHE"), False)


settings = Settings()
