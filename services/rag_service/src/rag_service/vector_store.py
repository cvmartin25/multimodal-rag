from __future__ import annotations

from typing import Any

from supabase import Client, create_client

from .config import Settings


class SupabaseVectorStore:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_url or not settings.supabase_service_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required.")
        self._settings = settings
        self._client: Client = create_client(settings.supabase_url, settings.supabase_service_key)

    def insert_record(self, row: dict[str, Any]) -> dict[str, Any]:
        result = self._client.table(self._settings.supabase_table).insert(row).execute()
        return result.data[0]

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        threshold: float,
        content_type: str | None = None,
        collection: str | None = None,
    ) -> list[dict[str, Any]]:
        result = self._client.rpc(
            self._settings.supabase_match_rpc,
            {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": top_k,
                "filter_type": content_type,
                "filter_collection": collection,
            },
        ).execute()
        return result.data or []

