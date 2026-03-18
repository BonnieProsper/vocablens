from typing import Protocol, List


class Translator(Protocol):

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> str:
        ...

    async def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
    ) -> List[str]:
        ...

    async def close(self) -> None:
        ...
