from __future__ import annotations

import base64
from urllib.request import Request, urlopen


def load_content_bytes(content_base64: str | None, content_url: str | None) -> bytes:
    if content_base64:
        return base64.b64decode(content_base64)
    if content_url:
        req = Request(content_url, headers={"User-Agent": "coachapp-rag-service/1.0"})
        with urlopen(req, timeout=120) as response:
            return response.read()
    raise ValueError("Either contentBase64 or contentUrl is required.")
