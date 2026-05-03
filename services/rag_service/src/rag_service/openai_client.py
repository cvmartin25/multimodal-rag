from __future__ import annotations

class OpenAIClientFactory:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None

    def get(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("OPENAI_API_KEY is missing.")
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key)
        return self._client
