from __future__ import annotations

import json
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

    def upsert_source(self, row: dict[str, Any]) -> dict[str, Any]:
        result = self._client.table("rag_sources").upsert(row).execute()
        return result.data[0]

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        threshold: float,
        content_type: str | None = None,
        collection: str | None = None,
        coach_profile_id: str | None = None,
    ) -> list[dict[str, Any]]:
        result = self._client.rpc(
            self._settings.supabase_match_rpc,
            {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": top_k,
                "filter_type": content_type,
                "filter_collection": collection,
                "filter_coach_profile_id": coach_profile_id,
            },
        ).execute()
        return result.data or []

    def fetch_tenant_rows(
        self,
        coach_profile_id: str,
        collection: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        query = (
            self._client.table(self._settings.supabase_table)
            .select(
                "id, title, content_type, original_filename, text_content, metadata, "
                "embedding, coach_profile_id, source_kind, source_id"
            )
            .eq("coach_profile_id", coach_profile_id)
            .limit(max(limit, 1))
        )
        if collection:
            query = query.eq("collection", collection)
        result = query.execute()
        rows = result.data or []
        for row in rows:
            emb = row.get("embedding")
            if isinstance(emb, str):
                try:
                    row["embedding"] = json.loads(emb)
                except Exception:
                    row["embedding"] = []
        return rows

