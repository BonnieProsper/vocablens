from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class VocabularyItem:
    id: Optional[int]
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    created_at: datetime
    last_reviewed_at: Optional[datetime]
    review_count: int