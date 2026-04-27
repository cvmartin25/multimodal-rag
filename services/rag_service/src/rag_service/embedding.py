from __future__ import annotations

import time

import numpy as np
from google.api_core import exceptions as gax_exceptions
from google.genai import types

from .gemini_client import GeminiClientFactory

MODEL = "gemini-embedding-2-preview"
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 10

_RETRYABLE = (
    gax_exceptions.ResourceExhausted,
    gax_exceptions.ServiceUnavailable,
    gax_exceptions.DeadlineExceeded,
    gax_exceptions.InternalServerError,
    ConnectionError,
)


class Embedder:
    def __init__(self, gemini_factory: GeminiClientFactory) -> None:
        self._gemini_factory = gemini_factory

    @staticmethod
    def _normalize(values: list[float]) -> list[float]:
        a = np.array(values, dtype=np.float64)
        norm = np.linalg.norm(a)
        if norm > 0:
            a = a / norm
        return a.tolist()

    def _embed_with_retry(self, contents, task_type: str) -> list[float]:
        for attempt in range(MAX_RETRIES):
            try:
                response = self._gemini_factory.get().models.embed_content(
                    model=MODEL,
                    contents=contents,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                return self._normalize(response.embeddings[0].values)
            except _RETRYABLE:
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(RETRY_BASE_DELAY_SECONDS * (2**attempt))

    def embed_query(self, text: str) -> list[float]:
        return self._embed_with_retry(text, task_type="RETRIEVAL_QUERY")

    def embed_text_document(self, text: str) -> list[float]:
        return self._embed_with_retry(text, task_type="RETRIEVAL_DOCUMENT")

    def embed_binary_document(self, data: bytes, mime_type: str) -> list[float]:
        part = types.Part.from_bytes(data=data, mime_type=mime_type)
        return self._embed_with_retry(part, task_type="RETRIEVAL_DOCUMENT")

