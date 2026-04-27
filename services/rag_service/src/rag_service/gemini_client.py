from __future__ import annotations

from google import genai


class GeminiClientFactory:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: genai.Client | None = None

    def get(self) -> genai.Client:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("GEMINI_API_KEY is missing.")
            self._client = genai.Client(api_key=self._api_key)
        return self._client

