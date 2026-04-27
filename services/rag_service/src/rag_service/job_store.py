from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Literal
from uuid import uuid4


JobStatus = Literal["queued", "running", "succeeded", "failed"]


@dataclass
class JobState:
    job_id: str
    status: JobStatus
    inserted_records: int = 0
    error: str | None = None


class InMemoryJobStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, JobState] = {}

    def create(self) -> JobState:
        with self._lock:
            state = JobState(job_id=str(uuid4()), status="queued")
            self._jobs[state.job_id] = state
            return state

    def set_running(self, job_id: str) -> JobState:
        with self._lock:
            state = self._jobs[job_id]
            state.status = "running"
            return state

    def set_succeeded(self, job_id: str, inserted_records: int) -> JobState:
        with self._lock:
            state = self._jobs[job_id]
            state.status = "succeeded"
            state.inserted_records = inserted_records
            state.error = None
            return state

    def set_failed(self, job_id: str, error: str) -> JobState:
        with self._lock:
            state = self._jobs[job_id]
            state.status = "failed"
            state.error = error
            return state

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(job_id)

