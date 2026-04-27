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
    extracted_text: str


def split_pdf_to_pages(pdf_bytes: bytes) -> list[PdfPage]:
    pages: list[PdfPage] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i in range(len(doc)):
            page = doc[i]
            text = page.get_text("text")
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            png_bytes = pix.tobytes("png")
            pages.append(
                PdfPage(
                    page_number=i + 1,  # 1-based
                    image_bytes=png_bytes,
                    image_mime_type="image/png",
                    extracted_text=text or "",
                )
            )
    return pages


@dataclass
class TimeWindow:
    start_sec: int
    end_sec: int
    payload: bytes
    mime_type: str


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

