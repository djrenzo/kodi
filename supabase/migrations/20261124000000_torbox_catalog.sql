-- TorBox catalog: everything the admin addon (plugin.video.torbox) knows about the
-- TorBox library, so a read-only user addon can show and play it without TorBox
-- credentials or TMDB lookups of its own.
--
-- Run once in the Supabase dashboard: SQL Editor > New query > paste > Run.
-- (Or with the Supabase CLI: `supabase link` + `supabase db push`.)
--
-- Access model
--   * Every request needs a logged-in Supabase user (email + password). The project's
--     publishable/anon key on its own reads nothing.
--   * public.members says who may use the catalog: 'reader' may read everything,
--     'admin' may also write. Users that are not in members see nothing.
--   * Members are added by hand in the SQL editor (see supabase/README.md).

-- ---------------------------------------------------------------------------------
-- Membership and role checks
-- ---------------------------------------------------------------------------------

create table public.members (
    user_id    uuid primary key references auth.users (id) on delete cascade,
    role       text not null default 'reader' check (role in ('admin', 'reader')),
    note       text,
    created_at timestamptz not null default now()
);

create or replace function public.is_member()
returns boolean
language sql stable security definer set search_path = ''
as $$
    select exists (select 1 from public.members m where m.user_id = (select auth.uid()));
$$;

create or replace function public.is_admin()
returns boolean
language sql stable security definer set search_path = ''
as $$
    select exists (
        select 1 from public.members m where m.user_id = (select auth.uid()) and m.role = 'admin'
    );
$$;

create or replace function public.set_updated_at()
returns trigger
language plpgsql set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

-- ---------------------------------------------------------------------------------
-- Catalog
-- ---------------------------------------------------------------------------------

-- TorBox accounts (WebDAV logins) of the admin addon; id = account slot (1..5).
create table public.accounts (
    id         smallint primary key,
    name       text not null,
    webdav_url text not null,
    username   text not null,
    updated_at timestamptz not null default now()
);

-- One row per movie / TV show. Several TorBox folders (e.g. one per season) share a title.
create table public.titles (
    id              bigint generated always as identity primary key,
    key             text not null unique,      -- 'tvshow:tmdb:60059', 'movie:tmdb:603', 'tvshow:tvdb:81189'
    media_type      text not null check (media_type in ('movie', 'tvshow')),
    title           text not null,
    original_title  text,
    year            smallint,
    tmdb_id         text,
    tvdb_id         text,
    imdb_id         text,
    plot            text,
    tagline         text,
    poster_url      text,
    fanart_url      text,
    genres          text[] not null default '{}',
    rating          numeric(4, 2),
    premiered       date,
    runtime         smallint,                  -- minutes (movies)
    status          text,                      -- TMDB status, e.g. 'Returning Series'
    episode_seasons smallint[] not null default '{}',  -- seasons whose episodes are in public.episodes
    tmdb_synced_at  timestamptz,               -- last time the TMDB details were fetched
    updated_at      timestamptz not null default now()
);
create index titles_media_type_idx on public.titles (media_type);
create index titles_tmdb_id_idx on public.titles (tmdb_id);
create index titles_imdb_id_idx on public.titles (imdb_id);

-- TV seasons as TMDB lists them (all seasons, also ones not on TorBox).
create table public.seasons (
    title_id      bigint not null references public.titles (id) on delete cascade,
    season_number smallint not null,
    name          text,
    overview      text,
    poster_url    text,
    air_date      date,
    episode_count smallint,
    primary key (title_id, season_number)
);

-- TV episode details from TMDB, for the seasons that have files on TorBox.
create table public.episodes (
    title_id       bigint not null references public.titles (id) on delete cascade,
    season_number  smallint not null,
    episode_number smallint not null,
    name           text,
    overview       text,
    still_url      text,
    air_date       date,
    runtime        smallint,
    rating         numeric(4, 2),
    primary key (title_id, season_number, episode_number)
);

-- Mirror of the admin addon's overrides.json: one row per TorBox root folder
-- (release name), automatic ('auto') and hand-made ('manual') identifications alike.
create table public.overrides (
    folder_name  text primary key,
    title_id     bigint references public.titles (id) on delete set null,
    source       text not null check (source in ('auto', 'manual')),
    media_type   text check (media_type in ('movie', 'tvshow')),
    title        text,
    year         smallint,
    tmdb_id      text,
    tvdb_id      text,
    imdb_id      text,
    thumb_url    text,
    plot         text,
    season       smallint,                     -- season override for the folder's files
    force_season boolean not null default false, -- true: season replaces the numbers in the file names
    raw          jsonb not null,               -- the untouched overrides.json entry
    synced_at    timestamptz not null,
    updated_at   timestamptz not null default now()
);
create index overrides_title_id_idx on public.overrides (title_id);

-- Subtitles chosen in the admin addon (stored per folder in overrides.json 'subs').
create table public.subtitles (
    id               bigint generated always as identity primary key,
    folder_name      text not null references public.overrides (folder_name) on delete cascade,
    title_id         bigint references public.titles (id) on delete cascade,
    season_number    smallint,
    episode_number   smallint,
    language         text not null,
    hearing_impaired boolean not null default false,
    file_name        text not null,
    url              text not null,
    synced_at        timestamptz not null,
    unique (folder_name, url)
);
create index subtitles_title_idx on public.subtitles (title_id, season_number, episode_number);

-- Every video file on TorBox. season/episode are the numbers the admin addon exports
-- the file as (season overrides applied). stream_url carries the WebDAV login and
-- can be played as is.
create table public.media_files (
    id             bigint generated always as identity primary key,
    account_id     smallint not null references public.accounts (id) on delete cascade,
    folder_name    text not null,              -- root folder; no FK, unidentified folders have no override
    title_id       bigint references public.titles (id) on delete set null,
    remote_path    text not null,              -- decoded WebDAV path
    file_name      text not null,
    size_bytes     bigint not null default 0,
    season_number  smallint,
    episode_number smallint,
    is_main        boolean not null default false,  -- movies: the main feature (largest file)
    webdav_url     text not null,
    stream_url     text not null,
    last_seen_at   timestamptz not null,
    unique (account_id, remote_path)
);
create index media_files_title_idx on public.media_files (title_id, season_number, episode_number);
create index media_files_folder_idx on public.media_files (folder_name);

-- One row per push from the admin addon. A user addon can compare the newest
-- finished_at with its cache to know when to reload the catalog.
create table public.sync_runs (
    id          bigint generated always as identity primary key,
    started_at  timestamptz not null,
    finished_at timestamptz,
    pushed_by   uuid default auth.uid(),
    stats       jsonb not null default '{}'
);

create trigger accounts_updated_at before update on public.accounts
    for each row execute function public.set_updated_at();
create trigger titles_updated_at before update on public.titles
    for each row execute function public.set_updated_at();
create trigger overrides_updated_at before update on public.overrides
    for each row execute function public.set_updated_at();

-- Deletes titles no override points to any more (seasons/episodes/subtitles cascade).
create or replace function public.prune_orphan_titles()
returns integer
language plpgsql set search_path = ''
as $$
declare
    removed integer;
begin
    if not public.is_admin() then
        raise exception 'admin only' using errcode = '42501';
    end if;
    delete from public.titles t
    where not exists (select 1 from public.overrides o where o.title_id = t.id);
    get diagnostics removed = row_count;
    return removed;
end;
$$;

-- ---------------------------------------------------------------------------------
-- Row level security: members read, admins write, nobody else sees anything
-- ---------------------------------------------------------------------------------

alter table public.members enable row level security;
create policy "members see their own membership" on public.members
    for select to authenticated using (user_id = (select auth.uid()));

do $$
declare
    t text;
begin
    foreach t in array array['accounts', 'titles', 'seasons', 'episodes', 'overrides',
                             'subtitles', 'media_files', 'sync_runs'] loop
        execute format('alter table public.%I enable row level security', t);
        execute format(
            'create policy "members read" on public.%I for select to authenticated '
            'using ((select public.is_member()))', t);
        execute format(
            'create policy "admins write" on public.%I for all to authenticated '
            'using ((select public.is_admin())) with check ((select public.is_admin()))', t);
    end loop;
end;
$$;

-- Table/function privileges: nothing for anonymous requests, the API for logged-in users
-- (row level security above decides what they actually get).
revoke all on all tables in schema public from anon;
revoke execute on all functions in schema public from anon, public;

grant select on public.members to authenticated;
grant select, insert, update, delete on public.accounts, public.titles, public.seasons,
    public.episodes, public.overrides, public.subtitles, public.media_files,
    public.sync_runs to authenticated;
grant usage, select on all sequences in schema public to authenticated;
grant execute on function public.is_member(), public.is_admin(),
    public.prune_orphan_titles() to authenticated;
