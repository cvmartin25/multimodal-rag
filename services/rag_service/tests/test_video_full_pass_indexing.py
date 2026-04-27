from __future__ import annotations

import base64
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag_service.config import Settings
from rag_service.models import IndexPayload
from rag_service.processors import TimeWindow
from rag_service.service import RagService
from rag_service.video_analysis import VideoSegment


class _FakeVectorStore:
    def __init__(self) -> None:
        self.rows = []

    def insert_record(self, row):
        self.rows.append(row)
        return row


class _FakeEmbedder:
    def embed_text_document(self, text: str):
        return [0.1, 0.2, 0.3]

    def embed_binary_document(self, data: bytes, mime_type: str):
        return [0.9, 0.1, 0.2]


class _FakeGeminiFactory:
    pass


class VideoFullPassIndexingTests(unittest.TestCase):
    def test_full_pass_segments_drive_range_windowing(self):
        store = _FakeVectorStore()
        service = RagService(
            settings=Settings(
                auth_token="x",
                supabase_url="u",
                supabase_service_key="k",
                gemini_api_key="g",
                window_seconds=120,
                overlap_seconds=10,
            ),
            vector_store=store,
            embedder=_FakeEmbedder(),
            gemini_factory=_FakeGeminiFactory(),
        )

        payload = IndexPayload.model_validate(
            {
                "requestId": "idx-1",
                "tenant": {"coachProfileId": "cp1"},
                "sourceKind": "video",
                "sourceId": "vid_99",
                "title": "Langes Coaching Video",
                "originalFilename": "coaching.mp4",
                "mimeType": "video/mp4",
                "contentBase64": base64.b64encode(b"fake-video-content").decode("ascii"),
                "analyzeVideoRelevance": True,
                "contentBucket": "coach-videos",
                "contentKey": "mycoach/cp1/videos/vid_99/original.mp4",
            }
        )

        full_pass_segments = [
            VideoSegment(
                segment_id="seg_0000",
                start_sec=60,
                end_sec=240,
                label="teaching",
                summary="Erklaert Finanzierungsteil A.",
                tags=["finanzierung"],
                why_relevant="Kerninhalt",
            ),
            VideoSegment(
                segment_id="seg_0001",
                start_sec=300,
                end_sec=420,
                label="noise",
                summary="Offtopic",
                tags=["smalltalk"],
                why_relevant="Nicht fachlich",
            ),
        ]

        relevant_windows = [
            TimeWindow(start_sec=60, end_sec=180, payload=b"w1", mime_type="video/mp4"),
            TimeWindow(start_sec=170, end_sec=240, payload=b"w2", mime_type="video/mp4"),
        ]

        with patch("rag_service.service.get_video_duration_seconds", return_value=500), patch(
            "rag_service.service.analyze_full_video_with_flash", return_value=full_pass_segments
        ), patch("rag_service.service.chunk_video_by_ranges", return_value=relevant_windows) as range_chunk_mock:
            inserted = service.run_indexing(payload)

        self.assertEqual(inserted, 2)
        self.assertEqual(len(store.rows), 2)
        self.assertEqual(store.rows[0]["metadata"]["evidence_type"], "video_window")
        self.assertEqual(store.rows[0]["metadata"]["segment_summary"], "Erklaert Finanzierungsteil A.")
        self.assertEqual(store.rows[0]["metadata"]["locator"]["startSec"], 60)
        self.assertEqual(store.rows[1]["metadata"]["locator"]["endSec"], 240)

        called_ranges = range_chunk_mock.call_args.kwargs["ranges"]
        self.assertEqual(len(called_ranges), 1)  # noise segment excluded before chunking
        self.assertEqual(called_ranges[0].start_sec, 60)
        self.assertEqual(called_ranges[0].end_sec, 240)


if __name__ == "__main__":
    unittest.main()

