-- =============================================================================
-- RAG: Quellen + Chunks (Gemini Embedding 2, 3072 Dimensionen)
-- Einmal im Supabase SQL-Editor ausführen (leere DB / Tabellen vorher entfernt).
-- Vektorindex: HNSW auf halfvec-Cast — float32-vector() ist in pgvector auf
-- 2000 Dim. indexierbar; 3072 → halfvec(3072) bis 4000 Dim. (pgvector ≥ 0.7).
-- =============================================================================

create extension if not exists vector with schema extensions;

-- -----------------------------------------------------------------------------
-- rag_sources: eine logische Datei/Quelle pro Coach
-- -----------------------------------------------------------------------------
create table public.rag_sources (
  id text primary key,
  coach_profile_id text not null,
  source_kind text not null,
  title text not null,
  original_filename text not null,
  mime_type text not null,
  storage_bucket text,
  storage_key text,
  language text not null default 'de',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index idx_rag_sources_tenant
  on public.rag_sources (coach_profile_id, source_kind);

-- -----------------------------------------------------------------------------
-- rag_chunks: Chunk-Zeilen inkl. Embedding vector(3072)
-- -----------------------------------------------------------------------------
create table public.rag_chunks (
  id bigserial primary key,
  source_id text not null references public.rag_sources (id) on delete cascade,
  coach_profile_id text not null,
  source_kind text not null,
  title text not null,
  original_filename text not null,
  content_type text not null,
  chunk_index integer not null,
  chunk_total integer not null,
  text_content text,
  metadata jsonb not null default '{}'::jsonb,
  embedding vector(3072) not null,
  collection text not null default 'default',
  created_at timestamptz not null default now()
);

create index idx_rag_chunks_tenant_collection
  on public.rag_chunks (coach_profile_id, collection);

create index idx_rag_chunks_source
  on public.rag_chunks (source_kind, source_id);

create index idx_rag_chunks_metadata_gin
  on public.rag_chunks using gin (metadata);

create index idx_rag_chunks_embedding_hnsw_halfvec
  on public.rag_chunks using hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops)
  with (m = 16, ef_construction = 64);

-- -----------------------------------------------------------------------------
-- RPC: semantische Suche (Cosinus über halfvec, passend zum Index)
-- -----------------------------------------------------------------------------
create or replace function public.match_rag_chunks (
  query_embedding vector(3072),
  match_threshold double precision,
  match_count integer,
  filter_type text default null,
  filter_collection text default null,
  filter_coach_profile_id text default null
)
returns table (
  id bigint,
  title text,
  content_type text,
  original_filename text,
  text_content text,
  metadata jsonb,
  embedding vector(3072),
  collection text,
  coach_profile_id text,
  source_kind text,
  source_id text,
  similarity double precision
)
language sql
stable
as $$
  select
    c.id,
    c.title,
    c.content_type,
    c.original_filename,
    c.text_content,
    c.metadata,
    c.embedding,
    c.collection,
    c.coach_profile_id,
    c.source_kind,
    c.source_id,
    (1 - (c.embedding::halfvec(3072) <=> query_embedding::halfvec(3072)))::double precision
      as similarity
  from public.rag_chunks c
  where (filter_type is null or c.content_type = filter_type)
    and (filter_collection is null or c.collection = filter_collection)
    and (filter_coach_profile_id is null or c.coach_profile_id = filter_coach_profile_id)
    and (
      1 - (c.embedding::halfvec(3072) <=> query_embedding::halfvec(3072))
    ) >= match_threshold
  order by c.embedding::halfvec(3072) <=> query_embedding::halfvec(3072)
  limit greatest(match_count, 1);
$$;

-- PostgREST (Service Key): execute für RPC
grant execute on function public.match_rag_chunks (
  vector(3072),
  double precision,
  integer,
  text,
  text,
  text
) to service_role;
