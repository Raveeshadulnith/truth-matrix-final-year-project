-- Add bounded perceptual-candidate lookup support to an existing database.
-- This migration is additive, does not rewrite rows, and is safe to re-run.

begin;

-- This B-tree index filters by owner, media type, exact algorithm/version, and
-- recency. It does not calculate pHash Hamming distance, video alignment, or
-- Chromaprint similarity; those comparisons remain bounded application work.
create index if not exists idx_analysis_results_user_fingerprint_candidates
on public.analysis_results(user_id, media_type, fingerprint_algorithm, created_at desc)
where fingerprint_algorithm is not null;

-- Keep the existing ownership policies active; this does not replace them.
alter table public.analysis_results enable row level security;

commit;
