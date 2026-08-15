-- Owner-scoped encrypted precise location storage.
-- Back up the database before applying. This migration does not alter or drop data.

create table if not exists public.analysis_sensitive_location (
  analysis_id uuid primary key references public.analysis_results(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  encrypted_payload text not null,
  encryption_version text not null,
  created_at timestamp with time zone not null default now(),
  constraint analysis_sensitive_location_payload_size_check
    check (char_length(encrypted_payload) between 1 and 8192),
  constraint analysis_sensitive_location_version_size_check
    check (char_length(encryption_version) between 1 and 64)
);

alter table public.analysis_sensitive_location enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'analysis_sensitive_location'
      and policyname = 'Users can view own sensitive location'
  ) then
    create policy "Users can view own sensitive location"
    on public.analysis_sensitive_location for select to authenticated
    using (auth.uid() = user_id);
  end if;
end
$$;

comment on table public.analysis_sensitive_location is
  'AES-GCM encrypted precise coordinates, separated from ordinary forensic evidence.';
