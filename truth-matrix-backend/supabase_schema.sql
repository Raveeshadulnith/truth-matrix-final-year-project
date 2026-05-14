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
  explanation text null,
  frames_analyzed integer null,
  created_at timestamp with time zone not null default now(),
  constraint analysis_results_media_type_check check (media_type in ('image', 'video', 'audio')),
  constraint analysis_results_label_check check (label in ('Authentic', 'Suspected Deepfake')),
  constraint analysis_results_confidence_check check (confidence >= 0 and confidence <= 100)
);

create index if not exists idx_user_profiles_email on public.user_profiles(email);
create index if not exists idx_analysis_results_user_id on public.analysis_results(user_id);
create index if not exists idx_analysis_results_created_at on public.analysis_results(created_at desc);
create index if not exists idx_analysis_results_media_type on public.analysis_results(media_type);

alter table public.user_profiles enable row level security;
alter table public.analysis_results enable row level security;

-- Drop policies first so this script can be re-run safely during development.
drop policy if exists "Users can view own profile" on public.user_profiles;
drop policy if exists "Users can update own profile" on public.user_profiles;
drop policy if exists "Users can insert own profile" on public.user_profiles;
drop policy if exists "Users can view own analysis results" on public.analysis_results;
drop policy if exists "Users can insert own analysis results" on public.analysis_results;
drop policy if exists "Users can delete own analysis results" on public.analysis_results;

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
