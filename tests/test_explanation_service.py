from vocablens.providers.llm.base import LLMJsonResult, LLMUsage
from vocablens.services.explanation_service import ExplainMyThinkingService
from tests.conftest import run_async


class FakeLLM:
    async def generate_json_with_usage(self, prompt: str):
        return LLMJsonResult(
            content={
                "grammar_mistake": "You used the wrong tense.",
                "natural_phrasing": "I went to school yesterday.",
                "native_level_explanation": "Native speakers pick the tense that matches the time marker automatically.",
            },
            usage=LLMUsage(total_tokens=15),
        )


def test_explain_my_thinking_returns_human_tutor_style_explanation():
    service = ExplainMyThinkingService(FakeLLM())

    result = run_async(
        service.explain(
            "I go to school yesterday",
            {
                "grammar_mistakes": ["present tense used with a past-time expression"],
                "vocab_misuse": [],
                "correction_feedback": ["Say 'I went to school yesterday.'"],
                "suggestions": [],
            },
        )
    )

    assert result["grammar_mistake"] == "You used the wrong tense."
    assert result["natural_phrasing"] == "I went to school yesterday."
    assert "Native speakers" in result["native_level_explanation"]
