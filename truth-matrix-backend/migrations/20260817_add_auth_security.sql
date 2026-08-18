-- Truth Matrix application-enforced email MFA and session security.
-- Safe to re-run. Backend-only tables use service_role; anon/authenticated have no grants.

create extension if not exists "pgcrypto";

create table if not exists public.user_security_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  mfa_enabled boolean not null default true,
  mfa_enrolled_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.auth_challenges (
  id uuid primary key,
  user_id uuid null references auth.users(id) on delete cascade,
  purpose text not null check (purpose in ('signup', 'login', 'step_up_disable_mfa')),
  email_hash text not null check (char_length(email_hash) = 64),
  otp_digest text not null check (char_length(otp_digest) = 64),
  ip_hash text null check (ip_hash is null or char_length(ip_hash) = 64),
  bound_session_digest text null check (bound_session_digest is null or char_length(bound_session_digest) = 64),
  expires_at timestamptz not null,
  max_attempts smallint not null check (max_attempts between 1 and 10),
  attempt_count smallint not null default 0 check (attempt_count >= 0),
  resend_count smallint not null default 0 check (resend_count >= 0),
  last_sent_at timestamptz not null default now(),
  consumed_at timestamptz null,
  revoked_at timestamptz null,
  created_at timestamptz not null default now()
);

create table if not exists public.app_sessions (
  session_digest text primary key check (char_length(session_digest) = 64),
  refresh_token_digest text null check (refresh_token_digest is null or char_length(refresh_token_digest) = 64),
  user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  last_activity_at timestamptz not null default now(),
  absolute_expires_at timestamptz not null,
  mfa_verified_at timestamptz null,
  revoked_at timestamptz null,
  revocation_reason text null check (revocation_reason is null or char_length(revocation_reason) <= 64)
);

create table if not exists public.auth_risk_state (
  risk_key text primary key check (char_length(risk_key) = 64),
  failure_count integer not null default 0 check (failure_count >= 0),
  window_started_at timestamptz not null default now(),
  captcha_required_until timestamptz null,
  blocked_until timestamptz null,
  updated_at timestamptz not null default now()
);

create table if not exists public.security_audit_events (
  id uuid primary key default gen_random_uuid(),
  event_type text not null check (char_length(event_type) between 1 and 64),
  outcome text not null check (char_length(outcome) between 1 and 32),
  user_id uuid null references auth.users(id) on delete set null,
  request_id text null check (request_id is null or char_length(request_id) <= 64),
  ip_hash text null check (ip_hash is null or char_length(ip_hash) = 64),
  session_hash text null check (session_hash is null or char_length(session_hash) = 64),
  user_agent text null check (user_agent is null or char_length(user_agent) <= 256),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now()
);

create table if not exists public.step_up_authorizations (
  token_digest text primary key check (char_length(token_digest) = 64),
  user_id uuid not null references auth.users(id) on delete cascade,
  session_digest text not null check (char_length(session_digest) = 64),
  action text not null check (action in ('disable_mfa')),
  expires_at timestamptz not null,
  consumed_at timestamptz null,
  created_at timestamptz not null default now()
);

alter table public.app_sessions alter column mfa_verified_at drop not null;
alter table public.app_sessions add column if not exists refresh_token_digest text null;

create index if not exists idx_auth_challenges_user_purpose on public.auth_challenges(user_id, purpose, created_at desc);
create index if not exists idx_auth_challenges_expiry on public.auth_challenges(expires_at) where consumed_at is null and revoked_at is null;
create index if not exists idx_app_sessions_user on public.app_sessions(user_id, created_at desc);
create unique index if not exists idx_app_sessions_refresh_token
  on public.app_sessions(refresh_token_digest) where refresh_token_digest is not null;
create index if not exists idx_audit_user_created on public.security_audit_events(user_id, created_at desc);
create index if not exists idx_audit_created on public.security_audit_events(created_at desc);
create index if not exists idx_step_up_expiry on public.step_up_authorizations(expires_at) where consumed_at is null;

alter table public.user_security_settings enable row level security;
alter table public.auth_challenges enable row level security;
alter table public.app_sessions enable row level security;
alter table public.auth_risk_state enable row level security;
alter table public.security_audit_events enable row level security;
alter table public.step_up_authorizations enable row level security;

revoke all on public.user_security_settings, public.auth_challenges, public.app_sessions,
  public.auth_risk_state, public.security_audit_events, public.step_up_authorizations
from public, anon, authenticated;
grant all on public.user_security_settings, public.auth_challenges, public.app_sessions,
  public.auth_risk_state, public.security_audit_events, public.step_up_authorizations
to service_role;

create or replace function public.create_auth_challenge(
  p_id uuid, p_user_id uuid, p_purpose text, p_email_hash text, p_otp_digest text,
  p_expires_at timestamptz, p_max_attempts integer, p_ip_hash text,
  p_bound_session_digest text default null
) returns setof public.auth_challenges
language plpgsql security definer set search_path = public, pg_temp as $$
begin
  if p_purpose not in ('signup', 'login', 'step_up_disable_mfa') then
    raise exception 'invalid challenge purpose';
  end if;
  update public.auth_challenges
  set revoked_at = now()
  where consumed_at is null and revoked_at is null and purpose = p_purpose
    and ((p_user_id is not null and user_id = p_user_id)
      or (p_user_id is null and user_id is null and email_hash = p_email_hash));
  return query
  insert into public.auth_challenges(
    id, user_id, purpose, email_hash, otp_digest, expires_at, max_attempts,
    ip_hash, bound_session_digest
  ) values (
    p_id, p_user_id, p_purpose, p_email_hash, p_otp_digest, p_expires_at,
    p_max_attempts, p_ip_hash, p_bound_session_digest
  ) returning *;
end;
$$;

create or replace function public.replace_auth_challenge(
  p_challenge_id uuid, p_otp_digest text, p_expires_at timestamptz,
  p_cooldown_seconds integer, p_max_resends integer
) returns setof public.auth_challenges
language plpgsql security definer set search_path = public, pg_temp as $$
begin
  return query
  update public.auth_challenges
  set otp_digest = p_otp_digest, expires_at = p_expires_at, attempt_count = 0,
      resend_count = resend_count + 1, last_sent_at = now()
  where id = p_challenge_id and consumed_at is null and revoked_at is null
    and expires_at > now() and resend_count < p_max_resends
    and last_sent_at <= now() - make_interval(secs => p_cooldown_seconds)
  returning *;
end;
$$;

drop function if exists public.consume_auth_challenge(uuid, text);
create or replace function public.consume_auth_challenge(
  p_challenge_id uuid, p_expected_digest text, p_digest_valid boolean
)
returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare c public.auth_challenges%rowtype;
begin
  select * into c from public.auth_challenges where id = p_challenge_id for update;
  if not found or c.revoked_at is not null or c.consumed_at is not null then
    return jsonb_build_object('status', 'invalid');
  end if;
  if c.expires_at <= now() then
    update public.auth_challenges set revoked_at = now() where id = c.id;
    return jsonb_build_object('status', 'expired', 'purpose', c.purpose);
  end if;
  if c.attempt_count >= c.max_attempts then
    return jsonb_build_object('status', 'attempts_exhausted', 'purpose', c.purpose);
  end if;
  -- The application performs hmac.compare_digest. This equality only guards
  -- against a concurrent resend changing the digest between read and lock.
  if c.otp_digest <> p_expected_digest then
    return jsonb_build_object('status', 'invalid', 'purpose', c.purpose);
  end if;
  if not p_digest_valid then
    update public.auth_challenges set attempt_count = attempt_count + 1,
      revoked_at = case when attempt_count + 1 >= max_attempts then now() else revoked_at end
    where id = c.id;
    return jsonb_build_object(
      'status', case when c.attempt_count + 1 >= c.max_attempts then 'attempts_exhausted' else 'invalid' end,
      'purpose', c.purpose
    );
  end if;
  update public.auth_challenges set consumed_at = now(), otp_digest = repeat('0', 64) where id = c.id;
  return jsonb_build_object(
    'status', 'verified', 'user_id', c.user_id, 'purpose', c.purpose,
    'bound_session_digest', c.bound_session_digest, 'email_hash', c.email_hash
  );
end;
$$;

drop function if exists public.register_app_session(text, uuid, timestamptz, timestamptz);
create or replace function public.register_app_session(
  p_session_digest text, p_refresh_token_digest text, p_user_id uuid,
  p_absolute_expires_at timestamptz, p_mfa_verified_at timestamptz
) returns void language sql security definer set search_path = public, pg_temp as $$
  insert into public.app_sessions(
    session_digest, refresh_token_digest, user_id, absolute_expires_at, mfa_verified_at
  )
  values (p_session_digest, p_refresh_token_digest, p_user_id, p_absolute_expires_at, p_mfa_verified_at)
  on conflict (session_digest) do update set
    user_id = excluded.user_id, refresh_token_digest = excluded.refresh_token_digest,
    last_activity_at = now(),
    absolute_expires_at = excluded.absolute_expires_at,
    mfa_verified_at = excluded.mfa_verified_at, revoked_at = null, revocation_reason = null;
$$;

create or replace function public.validate_app_refresh_session(
  p_refresh_token_digest text, p_idle_seconds integer
) returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare s public.app_sessions%rowtype;
begin
  select * into s from public.app_sessions
  where refresh_token_digest = p_refresh_token_digest for update;
  if not found or s.revoked_at is not null then
    return jsonb_build_object('status', 'invalid');
  end if;
  if s.absolute_expires_at <= now() then
    update public.app_sessions set revoked_at = now(), revocation_reason = 'absolute_timeout'
    where session_digest = s.session_digest;
    return jsonb_build_object('status', 'expired');
  end if;
  if s.last_activity_at <= now() - make_interval(secs => p_idle_seconds) then
    update public.app_sessions set revoked_at = now(), revocation_reason = 'idle_timeout'
    where session_digest = s.session_digest;
    return jsonb_build_object('status', 'idle_expired');
  end if;
  return jsonb_build_object(
    'status', 'active', 'user_id', s.user_id, 'session_digest', s.session_digest,
    'mfa_verified', s.mfa_verified_at is not null
  );
end;
$$;

create or replace function public.rotate_app_refresh_session(
  p_old_refresh_token_digest text, p_new_refresh_token_digest text,
  p_session_digest text, p_user_id uuid, p_idle_seconds integer
) returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare s public.app_sessions%rowtype;
begin
  select * into s from public.app_sessions
  where session_digest = p_session_digest and user_id = p_user_id for update;
  if not found or s.revoked_at is not null or s.refresh_token_digest <> p_old_refresh_token_digest then
    return jsonb_build_object('status', 'invalid');
  end if;
  if s.absolute_expires_at <= now() or s.last_activity_at <= now() - make_interval(secs => p_idle_seconds) then
    update public.app_sessions set revoked_at = now(),
      revocation_reason = case when s.absolute_expires_at <= now() then 'absolute_timeout' else 'idle_timeout' end
    where session_digest = s.session_digest;
    return jsonb_build_object('status', 'expired');
  end if;
  update public.app_sessions set refresh_token_digest = p_new_refresh_token_digest
  where session_digest = s.session_digest;
  return jsonb_build_object('status', 'rotated');
end;
$$;

create or replace function public.revoke_app_session_by_refresh(
  p_refresh_token_digest text, p_reason text
) returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare s public.app_sessions%rowtype;
begin
  select * into s from public.app_sessions
  where refresh_token_digest = p_refresh_token_digest for update;
  if not found then
    return jsonb_build_object('status', 'invalid');
  end if;
  if s.revoked_at is not null then
    return jsonb_build_object('status', 'already_revoked', 'user_id', s.user_id);
  end if;
  update public.app_sessions set revoked_at = now(), revocation_reason = left(p_reason, 64)
  where session_digest = s.session_digest;
  return jsonb_build_object('status', 'revoked', 'user_id', s.user_id);
end;
$$;

create or replace function public.validate_and_touch_app_session(
  p_session_digest text, p_user_id uuid, p_idle_seconds integer, p_touch_interval_seconds integer
) returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare s public.app_sessions%rowtype;
begin
  select * into s from public.app_sessions
  where session_digest = p_session_digest and user_id = p_user_id for update;
  if not found or s.revoked_at is not null then return jsonb_build_object('status', 'invalid'); end if;
  if s.absolute_expires_at <= now() then
    update public.app_sessions set revoked_at = now(), revocation_reason = 'absolute_timeout'
    where session_digest = p_session_digest;
    return jsonb_build_object('status', 'expired');
  end if;
  if s.last_activity_at <= now() - make_interval(secs => p_idle_seconds) then
    update public.app_sessions set revoked_at = now(), revocation_reason = 'idle_timeout'
    where session_digest = p_session_digest;
    return jsonb_build_object('status', 'idle_expired');
  end if;
  if s.last_activity_at <= now() - make_interval(secs => p_touch_interval_seconds) then
    update public.app_sessions set last_activity_at = now() where session_digest = p_session_digest;
  end if;
  return jsonb_build_object('status', 'active', 'mfa_verified', s.mfa_verified_at is not null);
end;
$$;

create or replace function public.get_auth_risk_status(p_risk_keys text[], p_window_seconds integer)
returns jsonb language sql security definer set search_path = public, pg_temp as $$
  select jsonb_build_object(
    'failure_count', coalesce(max(failure_count) filter (
      where window_started_at > now() - make_interval(secs => p_window_seconds)), 0),
    'captcha_required', coalesce(bool_or(captcha_required_until > now()), false),
    'blocked', coalesce(bool_or(blocked_until > now()), false)
  ) from public.auth_risk_state where risk_key = any(p_risk_keys);
$$;

create or replace function public.record_auth_failure(
  p_risk_keys text[], p_window_seconds integer, p_captcha_threshold integer, p_rate_limit integer
) returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare k text; max_failures integer := 0; require_captcha boolean := false; is_blocked boolean := false;
declare current_count integer;
begin
  foreach k in array p_risk_keys loop
    insert into public.auth_risk_state(risk_key, failure_count, window_started_at, updated_at)
    values (k, 1, now(), now())
    on conflict (risk_key) do update set
      failure_count = case
        when public.auth_risk_state.window_started_at <= now() - make_interval(secs => p_window_seconds) then 1
        else public.auth_risk_state.failure_count + 1 end,
      window_started_at = case
        when public.auth_risk_state.window_started_at <= now() - make_interval(secs => p_window_seconds) then now()
        else public.auth_risk_state.window_started_at end,
      updated_at = now()
    returning failure_count into current_count;
    update public.auth_risk_state set
      captcha_required_until = case when current_count >= p_captcha_threshold
        then now() + make_interval(secs => p_window_seconds) else captcha_required_until end,
      blocked_until = case when current_count >= p_rate_limit
        then now() + make_interval(secs => least(p_window_seconds, 900)) else blocked_until end
    where risk_key = k;
    max_failures := greatest(max_failures, current_count);
    require_captcha := require_captcha or current_count >= p_captcha_threshold;
    is_blocked := is_blocked or current_count >= p_rate_limit;
  end loop;
  return jsonb_build_object('failure_count', max_failures, 'captcha_required', require_captcha, 'blocked', is_blocked);
end;
$$;

create or replace function public.consume_step_up_authorization(
  p_token_digest text, p_user_id uuid, p_session_digest text, p_action text
) returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare a public.step_up_authorizations%rowtype;
begin
  select * into a from public.step_up_authorizations where token_digest = p_token_digest for update;
  if not found or a.user_id <> p_user_id or a.session_digest <> p_session_digest
     or a.action <> p_action or a.consumed_at is not null or a.expires_at <= now() then
    return jsonb_build_object('status', 'invalid');
  end if;
  update public.step_up_authorizations set consumed_at = now()
  where token_digest = p_token_digest;
  return jsonb_build_object('status', 'consumed');
end;
$$;

create or replace function public.apply_mfa_disable(
  p_token_digest text, p_user_id uuid, p_session_digest text, p_action text
) returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare a public.step_up_authorizations%rowtype;
begin
  select * into a from public.step_up_authorizations where token_digest = p_token_digest for update;
  if not found or a.user_id <> p_user_id or a.session_digest <> p_session_digest
     or a.action <> p_action or p_action <> 'disable_mfa'
     or a.consumed_at is not null or a.expires_at <= now() then
    return jsonb_build_object('status', 'invalid');
  end if;
  update public.step_up_authorizations set consumed_at = now() where token_digest = p_token_digest;
  insert into public.user_security_settings(user_id, mfa_enabled, updated_at)
  values (p_user_id, false, now())
  on conflict (user_id) do update set mfa_enabled = false, updated_at = now();
  update public.app_sessions set revoked_at = now(), revocation_reason = 'mfa_disabled'
  where user_id = p_user_id and session_digest <> p_session_digest and revoked_at is null;
  update public.app_sessions set mfa_verified_at = null
  where user_id = p_user_id and session_digest = p_session_digest and revoked_at is null;
  return jsonb_build_object('status', 'consumed');
end;
$$;

create or replace function public.cleanup_auth_security_data(p_audit_retention_days integer default 90)
returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare challenges_deleted integer; step_ups_deleted integer; risk_deleted integer; audits_deleted integer;
begin
  if p_audit_retention_days < 1 or p_audit_retention_days > 3650 then
    raise exception 'invalid audit retention';
  end if;
  delete from public.auth_challenges
  where greatest(expires_at, created_at) < now() - interval '1 day';
  get diagnostics challenges_deleted = row_count;
  delete from public.step_up_authorizations where expires_at < now() - interval '1 day';
  get diagnostics step_ups_deleted = row_count;
  delete from public.auth_risk_state where updated_at < now() - interval '7 days';
  get diagnostics risk_deleted = row_count;
  delete from public.security_audit_events
  where created_at < now() - make_interval(days => p_audit_retention_days);
  get diagnostics audits_deleted = row_count;
  return jsonb_build_object(
    'challenges_deleted', challenges_deleted, 'step_ups_deleted', step_ups_deleted,
    'risk_deleted', risk_deleted, 'audits_deleted', audits_deleted
  );
end;
$$;

create or replace function public.handle_new_user_security()
returns trigger language plpgsql security definer set search_path = public, pg_temp as $$
begin
  insert into public.user_security_settings(user_id, mfa_enabled)
  values (new.id, true) on conflict (user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_security_created on auth.users;
create trigger on_auth_user_security_created after insert on auth.users
for each row execute function public.handle_new_user_security();

insert into public.user_security_settings(user_id, mfa_enabled)
select id, true from auth.users on conflict (user_id) do nothing;

revoke all on function public.create_auth_challenge(uuid, uuid, text, text, text, timestamptz, integer, text, text) from public, anon, authenticated;
revoke all on function public.replace_auth_challenge(uuid, text, timestamptz, integer, integer) from public, anon, authenticated;
revoke all on function public.consume_auth_challenge(uuid, text, boolean) from public, anon, authenticated;
revoke all on function public.register_app_session(text, text, uuid, timestamptz, timestamptz) from public, anon, authenticated;
revoke all on function public.validate_app_refresh_session(text, integer) from public, anon, authenticated;
revoke all on function public.rotate_app_refresh_session(text, text, text, uuid, integer) from public, anon, authenticated;
revoke all on function public.revoke_app_session_by_refresh(text, text) from public, anon, authenticated;
revoke all on function public.validate_and_touch_app_session(text, uuid, integer, integer) from public, anon, authenticated;
revoke all on function public.get_auth_risk_status(text[], integer) from public, anon, authenticated;
revoke all on function public.record_auth_failure(text[], integer, integer, integer) from public, anon, authenticated;
revoke all on function public.consume_step_up_authorization(text, uuid, text, text) from public, anon, authenticated;
revoke all on function public.apply_mfa_disable(text, uuid, text, text) from public, anon, authenticated;
revoke all on function public.cleanup_auth_security_data(integer) from public, anon, authenticated;

grant execute on function public.create_auth_challenge(uuid, uuid, text, text, text, timestamptz, integer, text, text) to service_role;
grant execute on function public.replace_auth_challenge(uuid, text, timestamptz, integer, integer) to service_role;
grant execute on function public.consume_auth_challenge(uuid, text, boolean) to service_role;
grant execute on function public.register_app_session(text, text, uuid, timestamptz, timestamptz) to service_role;
grant execute on function public.validate_app_refresh_session(text, integer) to service_role;
grant execute on function public.rotate_app_refresh_session(text, text, text, uuid, integer) to service_role;
grant execute on function public.revoke_app_session_by_refresh(text, text) to service_role;
grant execute on function public.validate_and_touch_app_session(text, uuid, integer, integer) to service_role;
grant execute on function public.get_auth_risk_status(text[], integer) to service_role;
grant execute on function public.record_auth_failure(text[], integer, integer, integer) to service_role;
grant execute on function public.consume_step_up_authorization(text, uuid, text, text) to service_role;
grant execute on function public.apply_mfa_disable(text, uuid, text, text) to service_role;
grant execute on function public.cleanup_auth_security_data(integer) to service_role;

revoke all on function public.handle_new_user_security() from public, anon, authenticated;
