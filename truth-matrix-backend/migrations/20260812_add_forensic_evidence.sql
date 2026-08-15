-- Add forensic evidence persistence to an existing Truth Matrix database.
-- This migration is additive, does not rewrite rows, and is safe to re-run.

begin;

alter table public.analysis_results
  add column if not exists sha256 text,
  add column if not exists perceptual_fingerprint text,
  add column if not exists fingerprint_algorithm text,
  add column if not exists forensic_evidence jsonb,
  add column if not exists forensic_schema_version text;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'analysis_results_sha256_format_check'
      and conrelid = 'public.analysis_results'::regclass
  ) then
    alter table public.analysis_results
      add constraint analysis_results_sha256_format_check
      check (sha256 is null or sha256 ~ '^[0-9a-f]{64}$');
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'analysis_results_forensic_evidence_object_check'
      and conrelid = 'public.analysis_results'::regclass
  ) then
    alter table public.analysis_results
      add constraint analysis_results_forensic_evidence_object_check
      check (forensic_evidence is null or jsonb_typeof(forensic_evidence) = 'object');
  end if;
end
$$;

create index if not exists idx_analysis_results_user_sha256
on public.analysis_results(user_id, sha256)
where sha256 is not null;

-- RLS and existing ownership policies remain in place. Enabling RLS and
-- creating only missing policies are idempotent and do not replace policies.
alter table public.analysis_results enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'analysis_results'
      and policyname = 'Users can view own analysis results'
  ) then
    create policy "Users can view own analysis results"
    on public.analysis_results for select to authenticated
    using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'analysis_results'
      and policyname = 'Users can insert own analysis results'
  ) then
    create policy "Users can insert own analysis results"
    on public.analysis_results for insert to authenticated
    with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'analysis_results'
      and policyname = 'Users can delete own analysis results'
  ) then
    create policy "Users can delete own analysis results"
    on public.analysis_results for delete to authenticated
    using (auth.uid() = user_id);
  end if;
end
$$;

commit;
