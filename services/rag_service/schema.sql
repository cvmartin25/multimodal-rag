-- RAG schema for proof-first retrieval.
-- Embedding dimension is fixed to Gemini Embedding 2 (3072).

create extension if not exists vector with schema extensions;

create table if not exists public.rag_sources (
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

create index if not exists idx_rag_sources_tenant
  on public.rag_sources (coach_profile_id, source_kind);

create table if not exists public.rag_chunks (
  id bigserial primary key,
  source_id text not null references public.rag_sources(id) on delete cascade,
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

create index if not exists idx_rag_chunks_tenant_collection
  on public.rag_chunks (coach_profile_id, collection);

create index if not exists idx_rag_chunks_source
  on public.rag_chunks (source_kind, source_id);

create index if not exists idx_rag_chunks_metadata_gin
  on public.rag_chunks using gin (metadata);

create index if not exists idx_rag_chunks_embedding_ivfflat
  on public.rag_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create or replace function public.match_rag_chunks(
  query_embedding vector(3072),
  match_threshold float,
  match_count int,
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
  similarity float
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
    1 - (c.embedding <=> query_embedding) as similarity
  from public.rag_chunks c
  where (filter_type is null or c.content_type = filter_type)
    and (filter_collection is null or c.collection = filter_collection)
    and (filter_coach_profile_id is null or c.coach_profile_id = filter_coach_profile_id)
    and (1 - (c.embedding <=> query_embedding)) >= match_threshold
  order by c.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;
