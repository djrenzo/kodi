# TorBox catalog on Supabase

The TorBox addon (`plugin.video.torbox`) is the **admin** addon: Management > *Push overrides &
library to Supabase* uploads everything it knows to a Supabase (Postgres) database. A future
**user** addon only reads that database to list and play the library.

## What is stored

| Table | One row per | Contents |
|---|---|---|
| `titles` | movie / TV show | title, year, TMDB/TVDB/IMDb ids, plot, tagline, poster + fanart URLs, genres, rating, premiered, runtime, status |
| `seasons` | TV season (TMDB) | name, overview, poster URL, air date, episode count |
| `episodes` | TV episode (TMDB) | name, overview, still URL, air date, runtime, rating. Only for seasons that are on TorBox |
| `overrides` | TorBox root folder | the `overrides.json` entry: `auto`/`manual` source, title, ids, thumb, plot, season override, force-season flag, plus the raw JSON |
| `subtitles` | picked subtitle | language, hearing impaired, file name, download URL, season/episode |
| `media_files` | video file on TorBox | account, folder, title, season/episode (numbered like the library export, so season overrides are applied), size, main-feature flag, WebDAV URL, **`stream_url` with the WebDAV login embedded** |
| `accounts` | TorBox account | name, WebDAV URL, username |
| `sync_runs` | push | start/finish time, who pushed, counts |
| `members` | allowed user | `admin` (read + write) or `reader` (read only) |

Several folders can belong to one title (e.g. one folder per season). They share one `titles`
row, so the user addon shows one show with all its seasons.

Each push mirrors the local state:
- Overrides deleted locally are deleted from Supabase too, but the addon asks first.
- Files no longer on TorBox are removed, but only for accounts that could be listed completely.
- Titles that no override uses any more are removed.

TMDB details are only fetched for new titles, for titles with new seasons, and for titles whose
details are over 30 days old. You can also choose *refresh every title*.

## Access control

- Every request must be made by a logged-in Supabase user. The publishable (anon) key alone
  reads and writes nothing.
- Only users listed in `members` see data. `reader` users can read and `admin` users can also write.
  Everything is enforced by row level security in the database, not by the addons.
- Public sign-up is switched off, so nobody can create their own login.

> **Note:** `media_files.stream_url` contains your TorBox WebDAV username and password, because
> that is what makes the files directly playable. Anyone with a reader login can see them. Only
> give reader logins to people you'd trust with the TorBox login itself.

## Setup from scratch

### 1. Create the Supabase project
1. Go to <https://supabase.com/dashboard/sign-up> and sign up (GitHub or email).
2. **New project**: choose the organization (it creates a personal one), a name (e.g. `torbox`),
   a strong **database password** (save it in your password manager; the addon doesn't need it),
   and the region closest to you (e.g. *Central EU (Frankfurt)*). The Free plan is enough.
3. Wait until the project has finished setting up (about 1–2 minutes).

> **Note:** on the Free plan, a project pauses after 7 days without any activity. To prevent that,
> the TorBox addon's background service sends one small query 30 seconds after Kodi starts and
> every 24 hours while Kodi keeps running, as long as Supabase is configured. Pushes and the user
> addon's reads count as activity too. If the project does pause anyway (e.g. no Kodi box was on
> for a week), the Kodi log shows `Keep-alive ping failed`. Open the dashboard and click *Restore*.

### 2. Create the tables
1. Dashboard > **SQL Editor** > **New query**.
2. Paste the whole contents of
   [`migrations/20261124000000_torbox_catalog.sql`](migrations/20261124000000_torbox_catalog.sql)
   and click **Run**. It should report *Success. No rows returned*.

### 3. Lock down sign-ups
Dashboard > **Authentication** > **Sign In / Providers**: turn **off** *Allow new users to sign up*
and click *Save*. Leave the *Email* provider enabled, because the addons log in with email + password.

### 4. Create the logins
1. Dashboard > **Authentication** > **Users** > **Add user** > **Create new user**.
   - Admin login (used by this TorBox addon): your email and a strong password. Tick
     **Auto Confirm User**.
   - Optionally, one login per person/device for the user addon. Any email works, even a made-up
     one like `livingroom@torbox.local`, as long as *Auto Confirm User* is ticked.
2. Give them their role. SQL Editor > New query, replacing the emails:

   ```sql
   insert into public.members (user_id, role, note)
   select id, 'admin', 'TorBox admin addon' from auth.users where email = 'you@example.com';

   insert into public.members (user_id, role, note)
   select id, 'reader', 'living room Kodi' from auth.users where email = 'livingroom@torbox.local';
   ```

   To revoke access later: `delete from public.members where user_id = (select id from auth.users where email = '...');`
   (or delete the user under Authentication > Users).

### 5. Get the URL and key
- **Project URL**: Dashboard > **Project Settings** > **Data API** (or the *Connect* button):
  `https://<project-ref>.supabase.co`.
- **Publishable key**: **Project Settings** > **API Keys**: the `sb_publishable_...` key. Older
  projects can use the *anon* key under *Legacy API keys* instead.
  **Never** use the `sb_secret_...` / `service_role` key in an addon. It bypasses all security.
  The phone setup page refuses it.

### 6. Connect the TorBox addon
In Kodi: TorBox > **Management** > **Configure Supabase via Phone**, scan the QR code, and fill in the
project URL, publishable key, admin email and password. You can also enter them under addon
settings > *Supabase*.

### 7. Push
TorBox > **Management** > **Push overrides & library to Supabase**. The first push fetches TMDB
details for every title and lists every file on every account. With ~200 titles it takes about a
minute. Later pushes are much faster. When it finishes, a summary dialog shows the counts.

Check the data in Dashboard > **Table Editor**.

## Reading the catalog (for the user addon)

Every call needs these headers: `apikey: <publishable key>` and `Authorization: Bearer <access_token>`.

```text
# log in (returns access_token, valid 1 h, and refresh_token)
POST /auth/v1/token?grant_type=password           {"email": "...", "password": "..."}
POST /auth/v1/token?grant_type=refresh_token      {"refresh_token": "..."}

# has anything changed since the cached copy?
GET /rest/v1/sync_runs?select=finished_at&finished_at=not.is.null&order=finished_at.desc&limit=1

# movies that are on TorBox, with their main file
GET /rest/v1/titles?media_type=eq.movie&select=*,media_files!inner(stream_url,size_bytes)&media_files.is_main=is.true&order=title

# shows that are on TorBox
GET /rest/v1/titles?media_type=eq.tvshow&select=*,media_files!inner(id)&media_files.limit=1&order=title

# one show: seasons, episode details, playable files, subtitles
GET /rest/v1/seasons?title_id=eq.123&order=season_number
GET /rest/v1/episodes?title_id=eq.123&order=season_number,episode_number
GET /rest/v1/media_files?title_id=eq.123&select=season_number,episode_number,file_name,stream_url&order=season_number,episode_number
GET /rest/v1/subtitles?title_id=eq.123
```

Responses return at most 1000 rows. For bigger tables, page with `limit` / `offset`.
`torbox_supabase.SupabaseClient.select_all` already does this paging and can be reused.

## Changing the schema later
Add a new file to `migrations/` (e.g. `20270101000000_add_column.sql`) and run it in the SQL Editor.
Don't edit the first migration once it has been applied.
