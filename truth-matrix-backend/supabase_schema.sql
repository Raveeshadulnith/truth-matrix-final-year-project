-- Truth Matrix Supabase schema
-- Run this whole file in Supabase SQL Editor.

create extension if not exists "pgcrypto";

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.user_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  email text,
  avatar_url text null,
  role text not null default 'user',
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint user_profiles_role_check check (role in ('user', 'admin'))
);

create table if not exists public.analysis_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  media_type text not null,
  original_filename text null,
  firebase_url text null,
  heatmap_url text null,
  label text not null,
  confidence numeric not null,
  fake_probability numeric null,
  authentic_probability numeric null,
  model_version text null,
  explanation text null,
  frames_analyzed integer null,
  sha256 text null,
  perceptual_fingerprint text null,
  fingerprint_algorithm text null,
  forensic_evidence jsonb null,
  forensic_schema_version text null,
  created_at timestamp with time zone not null default now(),
  constraint analysis_results_media_type_check check (media_type in ('image', 'video', 'audio')),
  constraint analysis_results_label_check check (label in ('Authentic', 'Suspected Deepfake')),
  constraint analysis_results_confidence_check check (confidence >= 0 and confidence <= 100),
  constraint analysis_results_fake_probability_check
    check (fake_probability is null or (fake_probability >= 0 and fake_probability <= 100)),
  constraint analysis_results_authentic_probability_check
    check (authentic_probability is null or (authentic_probability >= 0 and authentic_probability <= 100)),
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
    check (forensic_evidence is null or jsonb_typeof(forensic_evidence) = 'object')
);

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

-- CREATE TABLE IF NOT EXISTS does not add columns to an existing table.
-- Keep these alterations so this baseline file remains safely re-runnable.
alter table public.analysis_results
  add column if not exists fake_probability numeric,
  add column if not exists authentic_probability numeric,
  add column if not exists model_version text,
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

create index if not exists idx_user_profiles_email on public.user_profiles(email);
create index if not exists idx_analysis_results_user_id on public.analysis_results(user_id);
create index if not exists idx_analysis_results_created_at on public.analysis_results(created_at desc);
create index if not exists idx_analysis_results_media_type on public.analysis_results(media_type);
create index if not exists idx_analysis_results_user_sha256
on public.analysis_results(user_id, sha256)
where sha256 is not null;

-- Narrows compatible perceptual candidates only. Hamming/sequence/acoustic
-- distance is still computed over a bounded result set in the application.
create index if not exists idx_analysis_results_user_fingerprint_candidates
on public.analysis_results(user_id, media_type, fingerprint_algorithm, created_at desc)
where fingerprint_algorithm is not null;

alter table public.user_profiles enable row level security;
alter table public.analysis_results enable row level security;
alter table public.analysis_sensitive_location enable row level security;

-- Preserve existing policies and create only those missing on a re-run.
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'user_profiles'
      and policyname = 'Users can view own profile'
  ) then
    create policy "Users can view own profile"
    on public.user_profiles for select to authenticated
    using (auth.uid() = id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'user_profiles'
      and policyname = 'Users can insert own profile'
  ) then
    create policy "Users can insert own profile"
    on public.user_profiles for insert to authenticated
    with check (auth.uid() = id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'user_profiles'
      and policyname = 'Users can update own profile'
  ) then
    create policy "Users can update own profile"
    on public.user_profiles for update to authenticated
    using (auth.uid() = id)
    with check (auth.uid() = id);
  end if;

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

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
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
    full_name = coalesce(nullif(excluded.full_name, ''), public.user_profiles.full_name),
    updated_at = now();

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

drop trigger if exists set_user_profiles_updated_at on public.user_profiles;
create trigger set_user_profiles_updated_at
before update on public.user_profiles
for each row execute function public.set_updated_at();
