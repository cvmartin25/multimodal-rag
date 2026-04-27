-- Optional schema extension for evidence-oriented retrieval.
-- Keeps compatibility with existing public.documents setup.

create extension if not exists vector with schema extensions;

-- Recommended additional columns for tenancy and source tracing.
alter table public.documents
  add column if not exists coach_profile_id text,
  add column if not exists source_kind text,
  add column if not exists source_id text;

-- Helpful index for tenant-scoped filtering.
create index if not exists idx_documents_coach_profile_id
  on public.documents (coach_profile_id);

create index if not exists idx_documents_source_kind_source_id
  on public.documents (source_kind, source_id);

-- JSON metadata should include:
-- locator, labels, storage_refs, hint_for_llm, model_version
