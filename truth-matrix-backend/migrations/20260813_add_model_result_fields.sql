-- Persist the local model's complete stable result contract in analysis history.
-- Additive, nullable, and safe to re-run against legacy databases.

alter table public.analysis_results
  add column if not exists fake_probability numeric,
  add column if not exists authentic_probability numeric,
  add column if not exists model_version text;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'analysis_results_fake_probability_check'
      and conrelid = 'public.analysis_results'::regclass
  ) then
    alter table public.analysis_results
      add constraint analysis_results_fake_probability_check
      check (fake_probability is null or (fake_probability >= 0 and fake_probability <= 100));
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'analysis_results_authentic_probability_check'
      and conrelid = 'public.analysis_results'::regclass
  ) then
    alter table public.analysis_results
      add constraint analysis_results_authentic_probability_check
      check (authentic_probability is null or (authentic_probability >= 0 and authentic_probability <= 100));
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'analysis_results_probability_sum_check'
      and conrelid = 'public.analysis_results'::regclass
  ) then
    alter table public.analysis_results
      add constraint analysis_results_probability_sum_check
      check (
        fake_probability is null
        or authentic_probability is null
        or abs(fake_probability + authentic_probability - 100) <= 0.1
      );
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'analysis_results_model_version_length_check'
      and conrelid = 'public.analysis_results'::regclass
  ) then
    alter table public.analysis_results
      add constraint analysis_results_model_version_length_check
      check (model_version is null or char_length(model_version) <= 128);
  end if;
end
$$;

-- Keep the existing ownership policies active; this migration does not replace them.
alter table public.analysis_results enable row level security;
