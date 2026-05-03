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
from rag_service.processors import TranscriptSegment
from rag_service.service import RagService
from rag_service.video_analysis import VideoSegment


class _FakeVectorStore:
    def __init__(self) -> None:
        self.rows = []

    def insert_record(self, row):
        self.rows.append(row)
        return row

    def upsert_source(self, row):
        return row


class _FakeEmbedder:
    def embed_text_document(self, text: str):
        return [0.1, 0.2, 0.3]

    def embed_binary_document(self, data: bytes, mime_type: str):
        return [0.9, 0.1, 0.2]


class _FakeGeminiFactory:
    pass


class _FakeOpenAIFactory:
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
                openai_api_key="o",
                window_seconds=120,
                overlap_seconds=10,
                transcript_target_span_seconds=40,
                transcript_max_span_seconds=60,
            ),
            vector_store=store,
            embedder=_FakeEmbedder(),
            gemini_factory=_FakeGeminiFactory(),
            openai_factory=_FakeOpenAIFactory(),
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

        transcript_segments = [
            TranscriptSegment(start_sec=60.0, end_sec=85.0, text="Segment A"),
            TranscriptSegment(start_sec=86.0, end_sec=110.0, text="Segment B"),
            TranscriptSegment(start_sec=150.0, end_sec=185.0, text="Segment C"),
        ]

        with patch("rag_service.service.get_video_duration_seconds", return_value=500), patch(
            "rag_service.service.analyze_full_video_with_flash", return_value=full_pass_segments
        ), patch("rag_service.service.transcribe_video_ranges", return_value=transcript_segments):
            inserted = service.run_indexing(payload)

        self.assertEqual(inserted, 2)
        self.assertEqual(len(store.rows), 2)
        self.assertEqual(store.rows[0]["metadata"]["evidence_type"], "video_span")
        self.assertEqual(store.rows[0]["metadata"]["segment_summary"], "Transcript span from Whisper segmentation.")
        self.assertEqual(store.rows[0]["metadata"]["locator"]["startSec"], 60)
        self.assertEqual(store.rows[1]["metadata"]["locator"]["endSec"], 185)


if __name__ == "__main__":
    unittest.main()

