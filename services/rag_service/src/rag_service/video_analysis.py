from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from google.genai import types

from .gemini_client import GeminiClientFactory
from .processors import TimeRange, TimeWindow

SegmentLabel = Literal["teaching", "qa", "admin", "noise"]


@dataclass
class VideoSegment:
    segment_id: str
    start_sec: int
    end_sec: int
    label: SegmentLabel
    summary: str
    tags: list[str]
    why_relevant: str | None = None


def _safe_segment(idx: int, window: TimeWindow, reason: str) -> VideoSegment:
    return VideoSegment(
        segment_id=f"seg_{idx:04d}",
        start_sec=window.start_sec,
        end_sec=window.end_sec,
        label="teaching",
        summary="Auto-segmented video window for retrieval.",
        tags=["video", "auto-segment"],
        why_relevant=reason,
    )


def _parse_flash_json(text: str | None) -> dict:
    if not text:
        return {}
    raw = text.strip()
    # Strip accidental code fences.
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
        return {}
    except json.JSONDecodeError:
        return {}


def _parse_full_pass(text: str | None) -> list[dict]:
    if not text:
        return []
    raw = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        segments = payload.get("segments")
        if isinstance(segments, list):
            return [s for s in segments if isinstance(s, dict)]
    if isinstance(payload, list):
        return [s for s in payload if isinstance(s, dict)]
    return []


def _clamp_label(value: str | None) -> SegmentLabel:
    if value in {"teaching", "qa", "admin", "noise"}:
        return value
    return "teaching"


def analyze_full_video_with_flash(
    video_bytes: bytes,
    mime_type: str,
    duration_sec: int,
    gemini_factory: GeminiClientFactory,
    model: str = "gemini-3.1-flash-lite-preview",
) -> list[VideoSegment]:
    """
    Full-video pass: asks Flash to produce relevant segments with timestamps.
    """
    client = gemini_factory.get()
    instruction = (
        "Analyze the full coaching video and return JSON only. "
        "Schema: {\"segments\":[{\"startSec\":int,\"endSec\":int,"
        "\"label\":\"teaching|qa|admin|noise\",\"summary\":string,"
        "\"tags\":[string],\"whyRelevant\":string}]}. "
        "Cover full timeline, avoid overlaps where possible."
    )
    try:
        part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        response = client.models.generate_content(
            model=model,
            contents=[part, instruction],
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are a strict video segmenter. Output only valid JSON."
                )
            ),
        )
        items = _parse_full_pass(response.text if response else None)
        segments: list[VideoSegment] = []
        for idx, item in enumerate(items):
            start = int(item.get("startSec", 0))
            end = int(item.get("endSec", start + 1))
            start = max(0, min(start, max(duration_sec - 1, 0)))
            end = max(start + 1, min(end, max(duration_sec, 1)))
            label = _clamp_label(str(item.get("label")) if item.get("label") is not None else None)
            tags = item.get("tags") if isinstance(item.get("tags"), list) else []
            tags = [str(t) for t in tags][:8]
            segments.append(
                VideoSegment(
                    segment_id=f"seg_{idx:04d}",
                    start_sec=start,
                    end_sec=end,
                    label=label,
                    summary=str(item.get("summary") or "Segment from full-pass analysis."),
                    tags=tags,
                    why_relevant=str(item.get("whyRelevant")) if item.get("whyRelevant") else None,
                )
            )
        return segments
    except Exception:
        return []


def to_time_ranges(segments: list[VideoSegment], include_qa: bool = True) -> list[TimeRange]:
    ranges: list[TimeRange] = []
    for seg in segments:
        if seg.label == "noise":
            continue
        if not include_qa and seg.label == "qa":
            continue
        ranges.append(TimeRange(start_sec=seg.start_sec, end_sec=seg.end_sec))
    return ranges


def analyze_windows_with_flash(
    windows: list[TimeWindow],
    gemini_factory: GeminiClientFactory,
    model: str = "gemini-3.1-flash-lite-preview",
) -> list[VideoSegment]:
    """
    Classify each window with Gemini Flash into teaching/qa/admin/noise.

    Falls back safely per window if a model call fails or output is malformed.
    """
    segments: list[VideoSegment] = []
    client = gemini_factory.get()
    instruction = (
        "You classify a coaching video window. "
        "Return JSON only with keys: "
        "label (teaching|qa|admin|noise), summary (max 2 sentences), "
        "tags (max 8 short tags), whyRelevant (1 sentence). "
        "No markdown."
    )

    for idx, window in enumerate(windows):
        try:
            part = types.Part.from_bytes(data=window.payload, mime_type=window.mime_type)
            response = client.models.generate_content(
                model=model,
                contents=[part, instruction],
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are a strict video indexing assistant. "
                        "Output valid JSON only."
                    )
                ),
            )
            parsed = _parse_flash_json(response.text if response else None)
            label = _clamp_label(str(parsed.get("label")) if parsed.get("label") is not None else None)
            summary = str(parsed.get("summary") or "Window analyzed for retrieval.")
            tags = parsed.get("tags") or []
            if not isinstance(tags, list):
                tags = []
            tags = [str(t) for t in tags][:8]
            why_relevant = str(parsed.get("whyRelevant")) if parsed.get("whyRelevant") else None
            segments.append(
                VideoSegment(
                    segment_id=f"seg_{idx:04d}",
                    start_sec=window.start_sec,
                    end_sec=window.end_sec,
                    label=label,
                    summary=summary,
                    tags=tags,
                    why_relevant=why_relevant,
                )
            )
        except Exception as exc:
            segments.append(_safe_segment(idx=idx, window=window, reason=f"Fallback due to: {exc}"))
    return segments


def build_segments_from_windows(windows: list[TimeWindow]) -> list[VideoSegment]:
    """
    Deterministic fallback strategy without any model calls.
    """
    return [_safe_segment(idx=idx, window=window, reason="Fallback segmentation mode is active.") for idx, window in enumerate(windows)]

