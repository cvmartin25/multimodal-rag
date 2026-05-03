from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass

import fitz

MIME_MAP = {
    "image/png": "image",
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/webp": "image",
    "image/gif": "image",
    "application/pdf": "pdf",
    "audio/mpeg": "audio",
    "audio/mp3": "audio",
    "audio/wav": "audio",
    "audio/x-wav": "audio",
    "video/mp4": "video",
    "video/quicktime": "video",
    "video/x-msvideo": "video",
    "text/plain": "text",
    "text/markdown": "text",
}


def detect_content_type(mime_type: str, filename: str) -> str:
    if mime_type in MIME_MAP:
        return MIME_MAP[mime_type]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in {"txt", "md"}:
        return "text"
    if ext in {"png", "jpg", "jpeg", "webp", "gif"}:
        return "image"
    if ext == "pdf":
        return "pdf"
    if ext in {"mp3", "wav", "ogg"}:
        return "audio"
    if ext in {"mp4", "mov", "avi"}:
        return "video"
    return "text"


def chunk_text(text: str, max_tokens: int = 1000, overlap_tokens: int = 100) -> list[str]:
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap_chars)
    return chunks


@dataclass
class PdfPage:
    page_number: int
    image_bytes: bytes
    image_mime_type: str
    image_extension: str
    extracted_text: str
    extraction_quality: str
    layout_complexity: float
    has_tables: bool
    has_figures: bool


def _pdf_image_export(format_name: str) -> tuple[str, str]:
    lowered = format_name.lower()
    if lowered in {"jpg", "jpeg"}:
        return "jpeg", "jpg"
    if lowered == "webp":
        return "webp", "webp"
    return "png", "png"


def _estimate_layout_complexity(page: fitz.Page, extracted_text: str) -> float:
    drawings = page.get_drawings()
    image_info = page.get_images(full=True)
    block_count = len(page.get_text("blocks"))
    char_count = len(extracted_text.strip())
    # Lightweight heuristic between 0.0 and 1.0.
    raw_score = (
        min(len(drawings), 20) * 0.02
        + min(len(image_info), 10) * 0.03
        + min(block_count, 100) * 0.004
        + (0.1 if char_count < 50 else 0.0)
    )
    return round(min(raw_score, 1.0), 3)


def _estimate_extraction_quality(text: str) -> str:
    clean = text.strip()
    if not clean:
        return "low"
    if len(clean) < 120:
        return "medium"
    return "high"


def split_pdf_to_pages(
    pdf_bytes: bytes,
    target_width: int = 1280,
    image_format: str = "jpeg",
    image_quality: int = 80,
) -> list[PdfPage]:
    pages: list[PdfPage] = []
    export_format, extension = _pdf_image_export(image_format)
    quality = max(30, min(image_quality, 95))
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i in range(len(doc)):
            page = doc[i]
            text = page.get_text("text")
            page_width = max(page.rect.width, 1.0)
            scale = max(target_width / page_width, 0.5)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
            image_bytes = pix.tobytes(output=export_format, jpg_quality=quality)
            layout_complexity = _estimate_layout_complexity(page=page, extracted_text=text or "")
            has_tables = bool(page.find_tables().tables)
            has_figures = bool(page.get_images(full=True))
            pages.append(
                PdfPage(
                    page_number=i + 1,  # 1-based
                    image_bytes=image_bytes,
                    image_mime_type=f"image/{'jpeg' if extension == 'jpg' else extension}",
                    image_extension=extension,
                    extracted_text=text or "",
                    extraction_quality=_estimate_extraction_quality(text or ""),
                    layout_complexity=layout_complexity,
                    has_tables=has_tables,
                    has_figures=has_figures,
                )
            )
    return pages


@dataclass
class TimeWindow:
    start_sec: int
    end_sec: int
    payload: bytes
    mime_type: str


@dataclass
class TimeRange:
    start_sec: int
    end_sec: int


@dataclass
class TranscriptSegment:
    start_sec: float
    end_sec: float
    text: str


def build_transcript_spans(
    segments: list[TranscriptSegment],
    target_seconds: int = 40,
    max_seconds: int = 60,
) -> list[TranscriptSegment]:
    if not segments:
        return []
    cleaned = [s for s in segments if s.text.strip() and s.end_sec > s.start_sec]
    if not cleaned:
        return []
    spans: list[TranscriptSegment] = []
    current: TranscriptSegment | None = None
    for seg in cleaned:
        if current is None:
            current = TranscriptSegment(start_sec=seg.start_sec, end_sec=seg.end_sec, text=seg.text.strip())
            continue
        next_duration = seg.end_sec - current.start_sec
        if next_duration <= target_seconds or next_duration <= max_seconds:
            current.end_sec = seg.end_sec
            current.text = f"{current.text} {seg.text.strip()}".strip()
        else:
            spans.append(current)
            current = TranscriptSegment(start_sec=seg.start_sec, end_sec=seg.end_sec, text=seg.text.strip())
    if current is not None:
        spans.append(current)
    return spans


def _chunk_media_with_pydub(audio_bytes: bytes, fmt: str, seconds: int) -> list[bytes]:
    from pydub import AudioSegment

    segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
    max_ms = seconds * 1000
    if len(segment) <= max_ms:
        return [audio_bytes]
    chunks: list[bytes] = []
    for start in range(0, len(segment), max_ms):
        end = min(start + max_ms, len(segment))
        part = segment[start:end]
        out = io.BytesIO()
        part.export(out, format=fmt)
        chunks.append(out.getvalue())
    return chunks


def chunk_audio(audio_bytes: bytes, mime_type: str = "audio/mp3", max_seconds: int = 75) -> list[TimeWindow]:
    fmt = "mp3" if "mp3" in mime_type or "mpeg" in mime_type else "wav"
    parts = _chunk_media_with_pydub(audio_bytes, fmt=fmt, seconds=max_seconds)
    windows: list[TimeWindow] = []
    current = 0
    for part in parts:
        end = current + max_seconds
        windows.append(TimeWindow(start_sec=current, end_sec=end, payload=part, mime_type=mime_type))
        current = end
    return windows


def chunk_video(video_bytes: bytes, mime_type: str = "video/mp4", window_seconds: int = 120, overlap_seconds: int = 10) -> list[TimeWindow]:
    from moviepy import VideoFileClip

    suffix = ".mp4" if "mp4" in mime_type else ".mov"
    step = max(window_seconds - overlap_seconds, 1)

    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_in.write(video_bytes)
    tmp_in.close()

    windows: list[TimeWindow] = []
    try:
        clip = VideoFileClip(tmp_in.name)
        duration = int(clip.duration or 0)
        if duration <= window_seconds:
            clip.close()
            return [TimeWindow(start_sec=0, end_sec=max(duration, 1), payload=video_bytes, mime_type=mime_type)]

        start = 0
        while start < duration:
            end = min(start + window_seconds, duration)
            sub = clip.subclipped(start, end)
            tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp_out_name = tmp_out.name
            tmp_out.close()
            try:
                sub.write_videofile(tmp_out_name, logger=None)
                with open(tmp_out_name, "rb") as f:
                    windows.append(
                        TimeWindow(
                            start_sec=int(start),
                            end_sec=int(end),
                            payload=f.read(),
                            mime_type=mime_type,
                        )
                    )
            finally:
                os.unlink(tmp_out_name)
                sub.close()
            if end >= duration:
                break
            start += step

        clip.close()
        return windows
    finally:
        os.unlink(tmp_in.name)


def get_video_duration_seconds(video_bytes: bytes, mime_type: str = "video/mp4") -> int:
    from moviepy import VideoFileClip

    suffix = ".mp4" if "mp4" in mime_type else ".mov"
    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_in.write(video_bytes)
    tmp_in.close()
    try:
        clip = VideoFileClip(tmp_in.name)
        duration = int(clip.duration or 0)
        clip.close()
        return max(duration, 1)
    finally:
        os.unlink(tmp_in.name)


def chunk_video_by_ranges(
    video_bytes: bytes,
    ranges: list[TimeRange],
    mime_type: str = "video/mp4",
    window_seconds: int = 120,
    overlap_seconds: int = 10,
) -> list[TimeWindow]:
    from moviepy import VideoFileClip

    if not ranges:
        return []

    suffix = ".mp4" if "mp4" in mime_type else ".mov"
    step = max(window_seconds - overlap_seconds, 1)

    tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_in.write(video_bytes)
    tmp_in.close()

    windows: list[TimeWindow] = []
    try:
        clip = VideoFileClip(tmp_in.name)
        duration = int(clip.duration or 0)
        if duration <= 0:
            clip.close()
            return []

        for r in ranges:
            start = max(0, int(r.start_sec))
            end_cap = min(int(r.end_sec), duration)
            if end_cap <= start:
                continue
            cursor = start
            while cursor < end_cap:
                end = min(cursor + window_seconds, end_cap)
                sub = clip.subclipped(cursor, end)
                tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp_out_name = tmp_out.name
                tmp_out.close()
                try:
                    sub.write_videofile(tmp_out_name, logger=None)
                    with open(tmp_out_name, "rb") as f:
                        windows.append(
                            TimeWindow(
                                start_sec=int(cursor),
                                end_sec=int(end),
                                payload=f.read(),
                                mime_type=mime_type,
                            )
                        )
                finally:
                    os.unlink(tmp_out_name)
                    sub.close()
                if end >= end_cap:
                    break
                cursor += step

        clip.close()
        return windows
    finally:
        os.unlink(tmp_in.name)

