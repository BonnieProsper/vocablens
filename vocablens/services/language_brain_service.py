from vocablens.services.mistake_engine import MistakeEngine
from vocablens.services.drill_generation_service import DrillGenerationService
from vocablens.services.skill_tracking_service import SkillTrackingService
from vocablens.services.conversation_memory_service import ConversationMemoryService


class LanguageBrainService:
    """
    Central AI learning intelligence.
    """

    def __init__(
        self,
        mistake_engine: MistakeEngine,
        drill_generator: DrillGenerationService,
        skill_tracker: SkillTrackingService,
        memory_service: ConversationMemoryService,
    ):

        self.mistake_engine = mistake_engine
        self.drill_generator = drill_generator
        self.skill_tracker = skill_tracker
        self.memory = memory_service

    def process_message(self, user_id: int, message: str, language: str):

        analysis = self.mistake_engine.analyze(message, language)

        if analysis["grammar_mistakes"]:
            self.skill_tracker.record_grammar_error(user_id)

        if analysis["vocab_misuse"]:
            self.skill_tracker.record_vocab_error(user_id)

        self.memory.add_message(user_id, message)

        drills = None

        if analysis["grammar_mistakes"] or analysis["vocab_misuse"]:

            drills = self.drill_generator.generate_drills(analysis)

        return {
            "analysis": analysis,
            "drills": drills,
        }