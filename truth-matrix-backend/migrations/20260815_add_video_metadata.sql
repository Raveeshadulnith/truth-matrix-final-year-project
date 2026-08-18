-- Preserve source-relative video sampling details in current and history results.

alter table public.analysis_results
  add column if not exists video_metadata jsonb;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'analysis_results_video_metadata_object_check'
      and conrelid = 'public.analysis_results'::regclass
  ) then
    alter table public.analysis_results
      add constraint analysis_results_video_metadata_object_check
      check (video_metadata is null or jsonb_typeof(video_metadata) = 'object');
  end if;
end
$$;

alter table public.analysis_results enable row level security;
