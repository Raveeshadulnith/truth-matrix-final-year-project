-- Truth Matrix fresh-database bootstrap migration.
--
-- DESTRUCTIVE: this intentionally deletes all existing Truth Matrix analysis
-- history and profiles from the public schema. It does not delete Supabase Auth
-- users, Storage objects, or Supabase-managed schemas.
--
-- Run this whole file once in the Supabase SQL Editor. The transaction rolls
-- back automatically if any statement fails.

begin;

-- Remove only Truth Matrix application objects. Drop the auth trigger first
-- because auth.users is owned and managed by Supabase.
drop trigger if exists on_auth_user_created on auth.users;
drop table if exists public.analysis_sensitive_location cascade;
drop table if exists public.analysis_results cascade;
drop table if exists public.user_profiles cascade;
drop function if exists public.handle_new_user();
drop function if exists public.set_updated_at();

create extension if not exists "pgcrypto";

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table public.user_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  email text,
  avatar_url text,
  role text not null default 'user',
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint user_profiles_role_check check (role in ('user', 'admin'))
);

create table public.analysis_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  media_type text not null,
  original_filename text,
  firebase_url text,
  heatmap_url text,
  label text not null,
  confidence numeric not null,
  fake_probability numeric,
  authentic_probability numeric,
  model_version text,
  explanation text,
  frames_analyzed integer,
  sha256 text,
  perceptual_fingerprint text,
  fingerprint_algorithm text,
  forensic_evidence jsonb,
  forensic_schema_version text,
  created_at timestamp with time zone not null default now(),
  constraint analysis_results_media_type_check
    check (media_type in ('image', 'video', 'audio')),
  constraint analysis_results_label_check
    check (label in ('Authentic', 'Suspected Deepfake')),
  constraint analysis_results_confidence_check
    check (confidence >= 0 and confidence <= 100),
  constraint analysis_results_fake_probability_check
    check (
      fake_probability is null
      or (fake_probability >= 0 and fake_probability <= 100)
    ),
  constraint analysis_results_authentic_probability_check
    check (
      authentic_probability is null
      or (authentic_probability >= 0 and authentic_probability <= 100)
    ),
  constraint analysis_results_probability_sum_check
    check (
      fake_probability is null
      or authentic_probability is null
      or abs(fake_probability + authentic_probability - 100) <= 0.1
    ),
  constraint analysis_results_model_version_length_check
    check (model_version is null or char_length(model_version) <= 128),
  constraint analysis_results_sha256_format_check
    check (sha256 is null or sha256 ~ '^[0-9a-f]{64}$'),
  constraint analysis_results_forensic_evidence_object_check
    check (
      forensic_evidence is null
      or jsonb_typeof(forensic_evidence) = 'object'
    )
);

create table public.analysis_sensitive_location (
  analysis_id uuid primary key
    references public.analysis_results(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  encrypted_payload text not null,
  encryption_version text not null,
  created_at timestamp with time zone not null default now(),
  constraint analysis_sensitive_location_payload_size_check
    check (char_length(encrypted_payload) between 1 and 8192),
  constraint analysis_sensitive_location_version_size_check
    check (char_length(encryption_version) between 1 and 64)
);

comment on table public.analysis_sensitive_location is
  'AES-GCM encrypted precise coordinates, separated from ordinary forensic evidence.';

create index idx_user_profiles_email
  on public.user_profiles(email);
create index idx_analysis_results_user_id
  on public.analysis_results(user_id);
create index idx_analysis_results_created_at
  on public.analysis_results(created_at desc);
create index idx_analysis_results_media_type
  on public.analysis_results(media_type);
create index idx_analysis_results_user_sha256
  on public.analysis_results(user_id, sha256)
  where sha256 is not null;
create index idx_analysis_results_user_fingerprint_candidates
  on public.analysis_results(
    user_id,
    media_type,
    fingerprint_algorithm,
    created_at desc
  )
  where fingerprint_algorithm is not null;

alter table public.user_profiles enable row level security;
alter table public.analysis_results enable row level security;
alter table public.analysis_sensitive_location enable row level security;

-- Supabase no longer guarantees automatic Data API grants for new projects.
-- Declare the intended privileges explicitly; RLS still restricts every
-- authenticated operation to rows owned by auth.uid(). Anonymous users receive
-- no direct access to these application tables.
revoke all privileges on table public.user_profiles from anon;
revoke all privileges on table public.analysis_results from anon;
revoke all privileges on table public.analysis_sensitive_location from anon;

grant select, insert, update
  on table public.user_profiles to authenticated;
grant select, insert, delete
  on table public.analysis_results to authenticated;
grant select
  on table public.analysis_sensitive_location to authenticated;

grant all privileges
  on table public.user_profiles,
           public.analysis_results,
           public.analysis_sensitive_location
  to service_role;

create policy "Users can view own profile"
on public.user_profiles
for select
to authenticated
using (auth.uid() = id);

create policy "Users can insert own profile"
on public.user_profiles
for insert
to authenticated
with check (auth.uid() = id);

create policy "Users can update own profile"
on public.user_profiles
for update
to authenticated
using (auth.uid() = id)
with check (auth.uid() = id);

create policy "Users can view own analysis results"
on public.analysis_results
for select
to authenticated
using (auth.uid() = user_id);

create policy "Users can insert own analysis results"
on public.analysis_results
for insert
to authenticated
with check (auth.uid() = user_id);

create policy "Users can delete own analysis results"
on public.analysis_results
for delete
to authenticated
using (auth.uid() = user_id);

create policy "Users can view own sensitive location"
on public.analysis_sensitive_location
for select
to authenticated
using (auth.uid() = user_id);

create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.user_profiles (id, full_name, email)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', ''),
    new.email
  )
  on conflict (id) do update
  set
    email = excluded.email,
    full_name = coalesce(
      nullif(excluded.full_name, ''),
      public.user_profiles.full_name
    ),
    updated_at = now();

  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

create trigger set_user_profiles_updated_at
before update on public.user_profiles
for each row execute function public.set_updated_at();

-- Rebuilding public.user_profiles does not fire the auth.users insert trigger
-- for accounts that already exist, so restore those profiles explicitly.
insert into public.user_profiles (id, full_name, email)
select
  id,
  coalesce(raw_user_meta_data ->> 'full_name', ''),
  email
from auth.users
on conflict (id) do update
set
  email = excluded.email,
  full_name = coalesce(
    nullif(excluded.full_name, ''),
    public.user_profiles.full_name
  ),
  updated_at = now();

commit;

-- Read-only verification. Each check should return true or the expected count.
select
  to_regclass('public.user_profiles') is not null as user_profiles_exists,
  to_regclass('public.analysis_results') is not null as analysis_results_exists,
  to_regclass('public.analysis_sensitive_location') is not null
    as sensitive_location_exists;

select
  relname as table_name,
  relrowsecurity as rls_enabled
from pg_class
where oid in (
  'public.user_profiles'::regclass,
  'public.analysis_results'::regclass,
  'public.analysis_sensitive_location'::regclass
)
order by relname;

select schemaname, tablename, policyname
from pg_policies
where schemaname = 'public'
  and tablename in (
    'user_profiles',
    'analysis_results',
    'analysis_sensitive_location'
  )
order by tablename, policyname;

select
  (select count(*) from auth.users) as auth_user_count,
  (select count(*) from public.user_profiles) as profile_count;
