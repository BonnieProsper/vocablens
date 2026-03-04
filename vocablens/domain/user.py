from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class User:
    id: int
    email: str
    password_hash: str
    created_at: datetime