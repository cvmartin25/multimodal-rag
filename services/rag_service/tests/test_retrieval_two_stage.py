from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag_service.config import Settings
from rag_service.models import RetrieveRequest
from rag_service.service import RagService


class _FakeVectorStore:
    def __init__(self) -> None:
        self.search_called = False

    def fetch_tenant_rows(self, coach_profile_id: str, collection: str | None, limit: int):
        return [
            {
                "id": "row_good",
                "title": "Beleihungsauslauf erklärt",
                "content_type": "video",
                "original_filename": "session1.mp4",
                "text_content": "In diesem Segment wird der Beleihungsauslauf erklärt.",
                "metadata": {
                    "coach_profile_id": coach_profile_id,
                    "evidence_type": "video_window",
                    "source_kind": "video",
                    "source_id": "vid_1",
                    "locator": {"startSec": 100, "endSec": 220, "paddingSec": 30},
                    "storage_refs": [{"kind": "s3", "bucket": "coach-videos", "key": "mycoach/cp1/videos/vid_1/original.mp4"}],
                    "labels": ["teaching"],
                },
                "embedding": [0.95, 0.05],
                "coach_profile_id": coach_profile_id,
            },
            {
                "id": "row_low",
                "title": "Irgendein anderes Thema",
                "content_type": "video",
                "original_filename": "session2.mp4",
                "text_content": "Dieser Abschnitt ist thematisch anders.",
                "metadata": {
                    "coach_profile_id": coach_profile_id,
                    "evidence_type": "video_window",
                    "source_kind": "video",
                    "source_id": "vid_2",
                    "locator": {"startSec": 300, "endSec": 420, "paddingSec": 30},
                    "storage_refs": [{"kind": "s3", "bucket": "coach-videos", "key": "mycoach/cp1/videos/vid_2/original.mp4"}],
                    "labels": ["teaching"],
                },
                "embedding": [0.05, 0.95],
                "coach_profile_id": coach_profile_id,
            },
        ]

    def search(self, *args, **kwargs):
        self.search_called = True
        return []


class _FakeEmbedder:
    def embed_query(self, text: str):
        # Strong match with first candidate vector.
        return [1.0, 0.0]


class _FakeGeminiFactory:
    pass


class RetrievalTwoStageTests(unittest.TestCase):
    def test_two_stage_prefilter_and_rerank_returns_expected_evidence(self):
        settings = Settings(
            auth_token="x",
            supabase_url="u",
            supabase_service_key="k",
            gemini_api_key="g",
            two_stage_enabled=True,
            two_stage_prefilter_limit=500,
            two_stage_candidate_count=20,
        )
        service = RagService(
            settings=settings,
            vector_store=_FakeVectorStore(),
            embedder=_FakeEmbedder(),
            gemini_factory=_FakeGeminiFactory(),
        )

        req = RetrieveRequest.model_validate(
            {
                "requestId": "req-1",
                "tenant": {"coachProfileId": "cp1"},
                "query": {"text": "Was ist der Beleihungsauslauf?"},
                "options": {"topK": 8, "topN": 3, "useTwoStage": True},
                "debug": True,
            }
        )
        res = service.retrieve(req)

        self.assertEqual(res.request_id, "req-1")
        self.assertEqual(len(res.evidences), 1)
        self.assertEqual(res.evidences[0].id, "row_good")
        self.assertEqual(res.evidences[0].type, "video_window")
        self.assertEqual(res.evidences[0].locator.start_sec, 100)
        self.assertEqual(res.debug["twoStage"], True)


if __name__ == "__main__":
    unittest.main()

