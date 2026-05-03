from __future__ import annotations

import tempfile
from pathlib import Path

from moviepy import VideoFileClip

from .openai_client import OpenAIClientFactory
from .processors import TimeRange, TranscriptSegment


def _extract_audio_bytes(video_bytes: bytes, mime_type: str) -> bytes:
    suffix = ".mp4" if "mp4" in mime_type else ".mov"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as in_file:
        in_file.write(video_bytes)
        in_path = Path(in_file.name)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as out_file:
        out_path = Path(out_file.name)

    clip = VideoFileClip(str(in_path))
    try:
        if clip.audio is None:
            return b""
        clip.audio.write_audiofile(str(out_path), logger=None)
    finally:
        clip.close()
        in_path.unlink(missing_ok=True)

    try:
        return out_path.read_bytes()
    finally:
        out_path.unlink(missing_ok=True)


def _transcribe_audio_bytes(
    audio_bytes: bytes,
    openai_factory: OpenAIClientFactory,
    model: str,
    language: str,
) -> list[TranscriptSegment]:
    if not audio_bytes:
        return []
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
        temp_audio.write(audio_bytes)
        temp_path = Path(temp_audio.name)
    try:
        with temp_path.open("rb") as audio_file:
            response = openai_factory.get().audio.transcriptions.create(
                model=model,
                file=audio_file,
                language=language,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        segments = getattr(response, "segments", None) or []
        out: list[TranscriptSegment] = []
        for seg in segments:
            start = float(getattr(seg, "start", 0.0))
            end = float(getattr(seg, "end", start + 0.1))
            text = str(getattr(seg, "text", "")).strip()
            if text and end > start:
                out.append(TranscriptSegment(start_sec=start, end_sec=end, text=text))
        return out
    finally:
        temp_path.unlink(missing_ok=True)


def transcribe_video(
    video_bytes: bytes,
    mime_type: str,
    openai_factory: OpenAIClientFactory,
    model: str,
    language: str,
) -> list[TranscriptSegment]:
    audio_bytes = _extract_audio_bytes(video_bytes=video_bytes, mime_type=mime_type)
    return _transcribe_audio_bytes(
        audio_bytes=audio_bytes,
        openai_factory=openai_factory,
        model=model,
        language=language,
    )


def transcribe_video_ranges(
    video_bytes: bytes,
    mime_type: str,
    ranges: list[TimeRange],
    openai_factory: OpenAIClientFactory,
    model: str,
    language: str,
) -> list[TranscriptSegment]:
    if not ranges:
        return transcribe_video(
            video_bytes=video_bytes,
            mime_type=mime_type,
            openai_factory=openai_factory,
            model=model,
            language=language,
        )

    suffix = ".mp4" if "mp4" in mime_type else ".mov"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as in_file:
        in_file.write(video_bytes)
        in_path = Path(in_file.name)

    out_segments: list[TranscriptSegment] = []
    clip = VideoFileClip(str(in_path))
    try:
        for time_range in ranges:
            start_sec = max(int(time_range.start_sec), 0)
            end_sec = max(int(time_range.end_sec), start_sec + 1)
            sub = clip.subclipped(start_sec, end_sec)
            out_path: Path | None = None
            try:
                if sub.audio is None:
                    continue
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as out_file:
                    out_path = Path(out_file.name)
                sub.audio.write_audiofile(str(out_path), logger=None)
                audio_bytes = out_path.read_bytes()
            finally:
                sub.close()
                if out_path is not None:
                    out_path.unlink(missing_ok=True)

            partial = _transcribe_audio_bytes(
                audio_bytes=audio_bytes,
                openai_factory=openai_factory,
                model=model,
                language=language,
            )
            for segment in partial:
                out_segments.append(
                    TranscriptSegment(
                        start_sec=segment.start_sec + start_sec,
                        end_sec=segment.end_sec + start_sec,
                        text=segment.text,
                    )
                )
    finally:
        clip.close()
        in_path.unlink(missing_ok=True)

    return out_segments
