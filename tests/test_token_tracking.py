from types import SimpleNamespace

from tests.conftest import run_async
from vocablens.infrastructure.observability.token_tracker import get_tokens, start_request
from vocablens.providers.llm.llm_guardrails import LLMGuardrails


class FakeChatCompletions:
    def __init__(self):
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18),
            choices=[SimpleNamespace(message=SimpleNamespace(content="Hello back"))],
        )


def test_llm_guardrails_extracts_usage_and_updates_request_token_tracker():
    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeChatCompletions()))
    guardrails = LLMGuardrails(client, cache_maxsize=8)
    start_request()

    result = run_async(guardrails.generate_text_result("hello"))

    assert result.content == "Hello back"
    assert result.usage.prompt_tokens == 11
    assert result.usage.completion_tokens == 7
    assert result.usage.total_tokens == 18
    assert get_tokens() == 18
