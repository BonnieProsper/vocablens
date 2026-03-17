from vocablens.infrastructure.jobs.base import JobQueue, JobOptions, RetryPolicy


class SkillSnapshotDispatcher:
    """Persists skill profiles asynchronously."""

    SUPPORTED = {"skill_update"}

    def __init__(self, jobs: JobQueue):
        self._jobs = jobs

    def supports(self, event_type: str) -> bool:
        return event_type in self.SUPPORTED

    def handle(self, event_type: str, user_id: int, payload: dict) -> None:
        opts = JobOptions(
            idempotency_key=f"skill:{user_id}",
            retry=RetryPolicy(max_attempts=3, backoff_seconds=5),
        )
        self._jobs.enqueue(
            "jobs.skill_snapshot",
            {"user_id": user_id, "profile": payload},
            opts,
        )
