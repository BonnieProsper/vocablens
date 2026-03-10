from vocablens.providers.llm.base import LLMProvider


class MistakeEngine:

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def analyze(self, message: str, language: str):

        prompt = f"""
Analyze the learner message.

Message:
{message}

Language:
{language}

Return JSON:

{{
 "grammar_mistakes":[],
 "vocab_misuse":[],
 "suggestions":[]
}}
"""

        return self.llm.generate_json(prompt)