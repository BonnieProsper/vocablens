from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator

from vocablens.services.conversation_service import ConversationService
from vocablens.services.tutor_mode_service import TutorModeService


class StreamingTutorService:
    _interruptions: dict[str, asyncio.Event] = {}

    def __init__(
        self,
        conversation_service: ConversationService,
        tutor_mode_service: TutorModeService,
        *,
        chunk_delay_seconds: float = 0.0,
    ):
        self._conversation = conversation_service
        self._tutor_mode = tutor_mode_service
        self._chunk_delay_seconds = chunk_delay_seconds

    async def stream_reply(
        self,
        *,
        user_id: int,
        message: str,
        source_lang: str,
        target_lang: str,
        tutor_mode: bool = True,
    ) -> AsyncIterator[dict]:
        stream_id = str(uuid.uuid4())
        cancel_event = asyncio.Event()
        self._interruptions[stream_id] = cancel_event
        task = asyncio.create_task(
            self._conversation.generate_reply(
                user_id=user_id,
                user_message=message,
                source_lang=source_lang,
                target_lang=target_lang,
                tutor_mode=tutor_mode,
            )
        )
        try:
            yield {"type": "stream_started", "stream_id": stream_id}
            response = await self._await_response(stream_id, task, cancel_event)
            if response is None:
                yield {"type": "interrupted", "stream_id": stream_id}
                return

            if tutor_mode:
                feedback = self._tutor_mode.streaming_feedback(response)
                for correction in feedback["live_corrections"]:
                    if cancel_event.is_set():
                        yield {"type": "interrupted", "stream_id": stream_id}
                        return
                    yield {
                        "type": "correction",
                        "stream_id": stream_id,
                        "content": correction,
                    }

            tokens = self._tokenize(response.get("reply", ""))
            midpoint = max(1, len(tokens) // 2) if tokens else 0
            for index, token in enumerate(tokens, start=1):
                if cancel_event.is_set():
                    yield {"type": "interrupted", "stream_id": stream_id}
                    return
                yield {
                    "type": "token",
                    "stream_id": stream_id,
                    "content": token,
                }
                if tutor_mode and index == midpoint:
                    mid_feedback = self._tutor_mode.streaming_feedback(response).get("mid_sentence_feedback")
                    if mid_feedback:
                        yield {
                            "type": "mid_sentence_feedback",
                            "stream_id": stream_id,
                            "content": mid_feedback,
                        }
                if self._chunk_delay_seconds > 0:
                    await asyncio.sleep(self._chunk_delay_seconds)

            yield {
                "type": "complete",
                "stream_id": stream_id,
                "response": response,
            }
        finally:
            self._interruptions.pop(stream_id, None)

    async def interrupt(self, stream_id: str) -> bool:
        event = self._interruptions.get(stream_id)
        if event is None:
            return False
        event.set()
        await asyncio.sleep(0)
        return True

    async def sse_events(
        self,
        *,
        user_id: int,
        message: str,
        source_lang: str,
        target_lang: str,
        tutor_mode: bool = True,
    ) -> AsyncIterator[str]:
        async for chunk in self.stream_reply(
            user_id=user_id,
            message=message,
            source_lang=source_lang,
            target_lang=target_lang,
            tutor_mode=tutor_mode,
        ):
            yield f"data: {json.dumps(chunk)}\n\n"

    async def _await_response(self, stream_id: str, task: asyncio.Task, cancel_event: asyncio.Event):
        while True:
            done, _ = await asyncio.wait({task}, timeout=0.05)
            if task in done:
                return await task
            if cancel_event.is_set():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                return None

    def _tokenize(self, text: str) -> list[str]:
        if not text:
            return []
        tokens = text.split(" ")
        chunks: list[str] = []
        for index, token in enumerate(tokens):
            suffix = "" if index == len(tokens) - 1 else " "
            chunks.append(token + suffix)
        return chunks
