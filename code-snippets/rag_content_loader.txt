from __future__ import annotations

import base64
from urllib.request import Request, urlopen

from .object_storage import WorkerObjectStorage


def load_content_bytes(
    content_base64: str | None,
    content_url: str | None,
    *,
    content_bucket: str | None = None,
    content_key: str | None = None,
    object_storage: WorkerObjectStorage | None = None,
) -> bytes:
    if content_base64:
        return base64.b64decode(content_base64)
    if content_url:
        req = Request(content_url, headers={"User-Agent": "coachapp-rag-service/1.0"})
        with urlopen(req, timeout=120) as response:
            return response.read()
    if content_bucket and content_key:
        if object_storage and object_storage.is_enabled():
            return object_storage.download_original(
                bucket=content_bucket,
                key=content_key,
                expected_bucket=content_bucket,
                expected_key=content_key,
            )
        raise ValueError(
            "contentBucket/contentKey gesetzt, aber Object Storage Worker nicht konfiguriert "
            "(RAG_S3_ENDPOINT_URL, RAG_S3_ACCESS_KEY_ID, RAG_S3_SECRET_ACCESS_KEY)."
        )
    raise ValueError("Either contentBase64, contentUrl, or contentBucket+contentKey with configured S3 worker.")
