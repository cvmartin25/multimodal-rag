from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    auth_token: str
    supabase_url: str
    supabase_service_key: str
    gemini_api_key: str
    supabase_table: str = "documents"
    supabase_match_rpc: str = "match_documents"
    default_collection: str = "default"
    default_topk: int = 8
    default_topn: int = 3
    window_seconds: int = 120
    overlap_seconds: int = 10
    video_padding_seconds: int = 30
    two_stage_enabled: bool = True
    two_stage_prefilter_limit: int = 1200
    two_stage_candidate_count: int = 120


def load_settings() -> Settings:
    two_stage_enabled_raw = os.getenv("RAG_TWO_STAGE_ENABLED", "true").strip().lower()
    two_stage_enabled = two_stage_enabled_raw in {"1", "true", "yes", "on"}
    return Settings(
        auth_token=os.getenv("RAG_SERVICE_AUTH_TOKEN", ""),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        supabase_table=os.getenv("RAG_SUPABASE_TABLE", "documents"),
        supabase_match_rpc=os.getenv("RAG_SUPABASE_MATCH_RPC", "match_documents"),
        default_collection=os.getenv("RAG_DEFAULT_COLLECTION", "default"),
        default_topk=_int_env("RAG_TOPK_DEFAULT", 8),
        default_topn=_int_env("RAG_TOPN_DEFAULT", 3),
        window_seconds=_int_env("RAG_INDEX_WINDOW_SECONDS", 120),
        overlap_seconds=_int_env("RAG_INDEX_WINDOW_OVERLAP_SECONDS", 10),
        video_padding_seconds=_int_env("RAG_VIDEO_PADDING_SECONDS", 30),
        two_stage_enabled=two_stage_enabled,
        two_stage_prefilter_limit=_int_env("RAG_TWO_STAGE_PREFILTER_LIMIT", 1200),
        two_stage_candidate_count=_int_env("RAG_TWO_STAGE_CANDIDATE_COUNT", 120),
    )

