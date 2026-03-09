from vocablens.providers.llm.base import LLMProvider
from vocablens.services.learning_graph_service import LearningGraphService


class LessonGenerationService:

    def __init__(
        self,
        llm: LLMProvider,
        graph_service: LearningGraphService,
    ):

        self.llm = llm
        self.graph = graph_service

    def generate_lesson(self, user_id: int):

        graph = self.graph.build_user_graph(user_id)

        clusters = list(graph.keys())[:5]

        words = []

        for c in clusters:
            words.extend(graph[c][:5])

        prompt = f"""
Create a language learning lesson.

Vocabulary:
{words}

Return JSON:

{{
"exercises":[
 {{
 "type":"fill_blank",
 "question":"",
 "answer":""
 }},
 {{
 "type":"multiple_choice",
 "question":"",
 "choices":[],
 "answer":""
 }}
]
}}
"""

        return self.llm.generate_json(prompt)