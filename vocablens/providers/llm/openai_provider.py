from openai import AsyncOpenAI

from vocablens.config.settings import settings
from vocablens.providers.llm.base import LLMJsonResult, LLMProvider, LLMTextResult
from vocablens.providers.llm.llm_guardrails import LLMGuardrails


class OpenAIProvider(LLMProvider):

    def __init__(self):
        api_key = settings.OPENAI_API_KEY

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=settings.LLM_TIMEOUT,
            max_retries=0,
        )
        self._guardrails = LLMGuardrails(
            self._client,
            default_timeout=settings.LLM_TIMEOUT,
            max_retries=settings.LLM_MAX_RETRIES,
            backoff_base=settings.LLM_BACKOFF_BASE,
        )

    async def generate(self, prompt: str) -> str:
        return (await self.generate_with_usage(prompt)).content

    async def generate_with_usage(self, prompt: str) -> LLMTextResult:
        return await self._guardrails.generate_text_result(
            prompt=prompt,
            version="v1",
        )

    async def generate_json(self, prompt: str) -> dict:
        return (await self.generate_json_with_usage(prompt)).content

    async def generate_json_with_usage(self, prompt: str) -> LLMJsonResult:
        return await self._guardrails.generate_json_result(
            prompt=prompt,
            version="v1",
            schema=None,
        )
