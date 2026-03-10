from vocablens.services.learning_graph_service import LearningGraphService
from vocablens.services.skill_tracking_service import SkillTrackingService


class CurriculumService:
    """
    Generates a personalized learning path.
    """

    def __init__(
        self,
        graph_service: LearningGraphService,
        skill_service: SkillTrackingService,
    ):
        self.graph = graph_service
        self.skills = skill_service

    def generate_plan(self, user_id: int):

        graph = self.graph.build_graph(user_id)

        weakest_cluster = self.graph.recommend_next_cluster(user_id)

        skills = self.skills.get_skill_profile(user_id)

        return {
            "focus_cluster": weakest_cluster,
            "skill_profile": skills,
            "recommended_action": "practice exercises and conversation",
        }