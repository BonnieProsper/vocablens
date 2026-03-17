from vocablens.infrastructure.unit_of_work import UnitOfWork


class PersonalizationService:
    """
    Maintains per-user learning profile (speed, retention, difficulty, content preference).
    """

    def __init__(self, uow_factory: type[UnitOfWork]):
        self._uow_factory = uow_factory

    async def get_profile(self, user_id: int):
        async with self._uow_factory() as uow:
            profile = await uow.profiles.get_or_create(user_id)
            await uow.commit()
            return profile

    async def update_from_session(
        self,
        user_id: int,
        session_duration_sec: float | None = None,
        correct_ratio: float | None = None,
    ):
        """
        Simple heuristic:
        - faster sessions with high accuracy -> bump learning_speed
        - low accuracy -> lower difficulty_preference and speed
        """
        async with self._uow_factory() as uow:
            profile = await uow.profiles.get_or_create(user_id)
            speed = profile.learning_speed
            retention = profile.retention_rate
            difficulty = profile.difficulty_preference

            if correct_ratio is not None:
                retention = max(0.3, min(1.0, 0.8 * retention + 0.2 * correct_ratio))
                if correct_ratio < 0.6:
                    difficulty = "easy"
                    speed = max(0.8, speed * 0.95)
                elif correct_ratio > 0.85:
                    difficulty = "hard" if speed > 1.1 else "medium"
                    speed = min(1.5, speed * 1.05)

            await uow.profiles.update(
                user_id=user_id,
                learning_speed=speed,
                retention_rate=retention,
                difficulty_preference=difficulty,
            )
            await uow.commit()

    async def set_preferences(
        self,
        user_id: int,
        difficulty: str | None = None,
        content: str | None = None,
    ):
        async with self._uow_factory() as uow:
            await uow.profiles.get_or_create(user_id)
            await uow.profiles.update(
                user_id=user_id,
                difficulty_preference=difficulty,
                content_preference=content,
            )
            await uow.commit()
