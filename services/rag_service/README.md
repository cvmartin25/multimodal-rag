# RAG Service (Python)

Python HTTP service for indexing and retrieval in the CoachApp architecture.

## Scope

- Provides retrieval for n8n tool-calling (`/v1/rag/retrieve`)
- Provides optional context preparation for n8n (`/v1/rag/prepare-context`)
- Provides indexing job execution (`/v1/rag/index`, `/v1/rag/jobs/{jobId}`)
- Stores vectors and evidence metadata in Supabase/pgvector
- Keeps Java as source of truth for tenancy and presigned URL resolution

## Run

```bash
pip install -r requirements.txt
uvicorn src.rag_service.main:app --reload --port 8010
```

## Required environment variables

- `RAG_SERVICE_AUTH_TOKEN` (shared secret for service-to-service calls)
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `GEMINI_API_KEY`

Optional:

- `RAG_SUPABASE_TABLE` (default: `documents`)
- `RAG_SUPABASE_MATCH_RPC` (default: `match_documents`)
- `RAG_DEFAULT_COLLECTION` (default: `default`)
- `RAG_INDEX_WINDOW_SECONDS` (default: `120`)
- `RAG_INDEX_WINDOW_OVERLAP_SECONDS` (default: `10`)
- `RAG_VIDEO_PADDING_SECONDS` (default: `30`)
- `RAG_TOPK_DEFAULT` (default: `8`)
- `RAG_TOPN_DEFAULT` (default: `3`)
- `RAG_TWO_STAGE_ENABLED` (default: `true`)
- `RAG_TWO_STAGE_PREFILTER_LIMIT` (default: `1200`)
- `RAG_TWO_STAGE_CANDIDATE_COUNT` (default: `120`)

## Notes

- This service intentionally returns `storageRefs` only, not presigned URLs.
- Java should resolve presigned URLs in batch for top evidence items.
- Video relevance pass runs as full-video Flash segmentation first, with safe fallback.
- Retrieval supports a two-stage mode (lexical prefilter + semantic reranking).
