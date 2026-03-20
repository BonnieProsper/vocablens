import asyncio

from tests.conftest import run_async
from vocablens.services.streaming_tutor_service import StreamingTutorService


class FakeConversationService:
    def __init__(self, response: dict, delay_seconds: float = 0.0):
        self.response = response
        self.delay_seconds = delay_seconds
        self.calls = []

    async def generate_reply(self, user_id: int, user_message: str, source_lang: str, target_lang: str, tutor_mode: bool = True):
        self.calls.append(
            {
                "user_id": user_id,
                "user_message": user_message,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "tutor_mode": tutor_mode,
            }
        )
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        return self.response


class FakeTutorModeService:
    def streaming_feedback(self, response_payload: dict) -> dict:
        return {
            "live_corrections": response_payload.get("live_corrections", []),
            "inline_explanations": response_payload.get("inline_explanations", []),
            "mid_sentence_feedback": response_payload.get("inline_explanations", [None])[0],
        }


def test_streaming_tutor_service_streams_corrections_and_tokens_in_order():
    response = {
        "reply": "Try this corrected sentence.",
        "live_corrections": ["Use the past tense here."],
        "inline_explanations": ["Past tense matches the time marker."],
        "tutor_mode": True,
    }
    service = StreamingTutorService(
        FakeConversationService(response),
        FakeTutorModeService(),
    )

    async def scenario():
        chunks = []
        async for chunk in service.stream_reply(
            user_id=1,
            message="I goed there",
            source_lang="en",
            target_lang="es",
            tutor_mode=True,
        ):
            chunks.append(chunk)
        return chunks

    chunks = run_async(scenario())

    assert chunks[0]["type"] == "stream_started"
    assert chunks[1]["type"] == "correction"
    token_chunks = [chunk["content"] for chunk in chunks if chunk["type"] == "token"]
    assert "".join(token_chunks) == "Try this corrected sentence."
    assert any(chunk["type"] == "mid_sentence_feedback" for chunk in chunks)
    assert chunks[-1]["type"] == "complete"


def test_streaming_tutor_service_supports_interruption():
    response = {
        "reply": "This response should be interrupted before it finishes streaming.",
        "live_corrections": ["Short correction."],
        "inline_explanations": ["Helpful explanation."],
        "tutor_mode": True,
    }
    service = StreamingTutorService(
        FakeConversationService(response, delay_seconds=0.01),
        FakeTutorModeService(),
        chunk_delay_seconds=0.01,
    )

    async def scenario():
        chunks = []
        stream_id = None
        async for chunk in service.stream_reply(
            user_id=1,
            message="interrupt me",
            source_lang="en",
            target_lang="es",
            tutor_mode=True,
        ):
            chunks.append(chunk)
            if chunk["type"] == "stream_started":
                stream_id = chunk["stream_id"]
            if chunk["type"] == "token":
                await service.interrupt(stream_id)
        return chunks

    chunks = run_async(scenario())

    assert any(chunk["type"] == "interrupted" for chunk in chunks)
    assert chunks[-1]["type"] == "interrupted"
