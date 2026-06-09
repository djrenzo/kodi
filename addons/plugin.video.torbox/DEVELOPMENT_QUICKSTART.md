# TorBox Kodi Addon - Quick Start

This is the fast onboarding companion to `DEVELOPMENT_KNOWLEDGE.md`.

## What This Addon Does
`plugin.video.torbox` browses and plays TorBox WebDAV media in Kodi, supports multi-account setup, library export (STRM/NFO), overrides, and subtitle workflows.

## Read These Files First
1. `addon.py` - action router + Kodi list UI orchestration.
2. `torbox_common.py` - shared constants/settings/accounts/helpers.
3. `torbox_text.py` - all user-facing strings + setup HTML templates.
4. `torbox_setup.py` - QR + local phone setup server.
5. `torbox_webdav.py` - PROPFIND + WebDAV parse/auth URL logic.
6. `torbox_library.py` - export and Kodi source creation.
7. `torbox_subtitles.py` - subtitle search/download/persistence.

## Action Routing Map
Main actions handled by `router()` in `addon.py`:
- `root`
- `browse`
- `library_browse`
- `play`
- `set_override`
- `add_subtitles`
- `view_overrides`
- `add_account`
- `settings`
- `refresh`
- `export_library`

## Data Locations
- Settings schema: `resources/settings.xml`
- Manual overrides: profile `overrides.json` (accessed via `load_overrides` / `save_overrides`)
- Library export root: addon setting `library_path`

## Current Conventions
- Keep orchestration in `addon.py`.
- Put shared helpers in `torbox_common.py`.
- Keep user-facing text/templates in `torbox_text.py`.
- Do not hardcode UI text in feature modules.
- Preserve current Kodi action query format.

## Setup Flow (Phone)
1. User selects add account.
2. QR opens phone page on `http://<local-ip>:8765`.
3. User submits URL/username/password.
4. Credentials persist to `account{n}_*` settings.
5. Setup server shuts down.

Notes:
- Setup page is polished and responsive.
- Existing URL/username prefill in form.
- Prefill is escaped before rendering.

## Export Behavior
- TV shows: recursive walk, episode filename parsing, per-episode STRM.
- Movies: choose largest direct video file, one STRM.
- NFO writing is conditional on IDs:
  - TVDB -> `tvshow.nfo`
  - TMDB -> `movie.nfo`
- First run adds `TorBox Library` source to Kodi.

## Known Editor Caveat
Outside Kodi runtime, unresolved import warnings for `xbmc*` modules are expected and usually not real runtime failures.

## Good First Checks After Changes
1. Verify action still resolves from Kodi query string.
2. Verify browse/play for at least one account.
3. Verify export produces expected STRM/NFO layout.
4. Verify setup phone form still opens and saves.
5. Verify all new text lives in `torbox_text.py`.

## Handoff Pointer
For full architecture and rationale, read `DEVELOPMENT_KNOWLEDGE.md`.
