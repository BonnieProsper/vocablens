from vocablens.services.personalization_service import PersonalizationService


class PersonalizationUpdateProcessor:
    """
    Refreshes the user personalization profile from recent learning signals.
    """

    SUPPORTED = {
        "conversation_turn",
        "word_learned",
        "word_reviewed",
    }

    def __init__(self, personalization: PersonalizationService):
        self._personalization = personalization

    def supports(self, event_type: str) -> bool:
        return event_type in self.SUPPORTED

    async def handle(self, event_type: str, user_id: int, payload: dict) -> None:
        await self._personalization.update_from_learning_signals(user_id)
