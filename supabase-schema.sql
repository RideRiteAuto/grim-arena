-- Grim World save backend. Paste this whole file into the Supabase
-- SQL Editor (Dashboard -> SQL Editor -> New query -> Run) exactly once.
-- Security model: the table allows NO direct access at all. The only doors
-- are two functions, and both require the caller to present the correct
-- password hash for the row they touch.

create table if not exists grim_saves (
  username   text primary key,
  pass_hash  text not null,
  save       jsonb,
  updated_at timestamptz not null default now()
);

alter table grim_saves enable row level security;
-- no policies on purpose: anon cannot read or write the table directly

create or replace function grim_login(u text, h text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  row_rec grim_saves%rowtype;
begin
  u := lower(trim(u));
  if u !~ '^[a-z0-9_]{3,16}$' then
    return jsonb_build_object('status', 'bad');
  end if;
  select * into row_rec from grim_saves where username = u;
  if not found then
    insert into grim_saves (username, pass_hash, save) values (u, h, null);
    return jsonb_build_object('status', 'new', 'save', null);
  end if;
  if row_rec.pass_hash <> h then
    return jsonb_build_object('status', 'bad');
  end if;
  return jsonb_build_object('status', 'ok', 'save', row_rec.save);
end;
$$;

create or replace function grim_save(u text, h text, s jsonb)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  n int;
begin
  u := lower(trim(u));
  if pg_column_size(s) > 262144 then   -- 256KB cap per save, ample and abuse-resistant
    return false;
  end if;
  update grim_saves set save = s, updated_at = now()
    where username = u and pass_hash = h;
  get diagnostics n = row_count;
  return n = 1;
end;
$$;

revoke all on grim_saves from anon, authenticated;
grant execute on function grim_login(text, text) to anon;
grant execute on function grim_save(text, text, jsonb) to anon;
