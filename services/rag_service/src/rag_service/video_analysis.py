from __future__ import annotations

from dataclasses import dataclass

from .processors import TimeWindow


@dataclass
class VideoSegment:
    segment_id: str
    start_sec: int
    end_sec: int
    label: str
    summary: str
    tags: list[str]
    why_relevant: str | None = None


def build_segments_from_windows(windows: list[TimeWindow]) -> list[VideoSegment]:
    """
    Fallback strategy for relevance analysis.

    The production target is a Gemini Flash analysis pass before embedding.
    For now, we create deterministic segments from windows so indexing is usable.
    """
    segments: list[VideoSegment] = []
    for idx, window in enumerate(windows):
        segments.append(
            VideoSegment(
                segment_id=f"seg_{idx:04d}",
                start_sec=window.start_sec,
                end_sec=window.end_sec,
                label="teaching",
                summary="Auto-segmented video window for retrieval.",
                tags=["video", "auto-segment"],
                why_relevant="Fallback segmentation mode is active.",
            )
        )
    return segments

