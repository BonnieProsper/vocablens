from vocablens.services.knowledge_graph_service import KnowledgeGraphService


class KnowledgeGraphProcessor:
    """
    Enriches knowledge graph observations when new words or conversations occur.
    Currently keeps in-memory observations; persistence can be added later.
    """

    SUPPORTED = {"word_learned", "conversation_turn"}

    def __init__(self, graph_service: KnowledgeGraphService):
        self._graph = graph_service

    def supports(self, event_type: str) -> bool:
        return event_type in self.SUPPORTED

    async def handle(self, event_type: str, user_id: int, payload: dict) -> None:
        if event_type == "word_learned" and payload.get("words"):
            await self._graph.refresh_user_graph(user_id)
            return

        if event_type == "conversation_turn" and payload.get("new_words"):
            await self._graph.invalidate_user_graph(user_id)
