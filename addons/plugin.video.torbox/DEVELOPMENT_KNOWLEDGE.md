# TorBox Kodi Addon - Development Knowledge

## Purpose
This document captures the current architecture, behavior, conventions, and implementation details for `plugin.video.torbox` so future work can resume quickly without re-discovery.

## Addon Identity
- Addon ID: `plugin.video.torbox`
- Main entrypoint: `addon.py`
- Platform/runtime: Kodi Python runtime (`xbmc`, `xbmcgui`, `xbmcplugin`, `xbmcvfs`)
- Current addon metadata: see `addon.xml`

## Current Module Structure
- `addon.py`
  - Router and UI list building.
  - Main action handling for browse/play/overrides/subtitles/settings/export.
- `torbox_common.py`
  - Shared constants, settings access, logging, URL helpers, overrides load/save, account helpers.
  - TypedDict definitions for account and WebDAV item shapes.
- `torbox_webdav.py`
  - WebDAV PROPFIND, path-safe URL encoding, XML parsing, authenticated stream URL builder.
- `torbox_library.py`
  - Library path logic, source creation in `sources.xml`, NFO/STRM export, recursive WebDAV walking.
- `torbox_subtitles.py`
  - Subtitle search/download/selection, subtitle metadata persistence in overrides.
- `torbox_setup.py`
  - Phone setup local HTTP server and QR flow for account setup.
  - Uses centralized HTML templates and supports prefilled URL/username.
- `torbox_text.py`
  - Centralized user-facing strings and setup HTML templates (main form + success + error pages).

## High-Level Runtime Flow
1. Kodi calls `addon.py` with query params.
2. `router()` maps `action` to feature handlers.
3. For browsing, WebDAV folder listing is fetched with PROPFIND and rendered as Kodi list items.
4. For play, stream URL is turned into an authenticated URL and resolved via `xbmcplugin.setResolvedUrl`.
5. For export, WebDAV content is converted into local STRM/NFO structure for Kodi library scanning.
6. For setup, user opens phone page from QR code and submits credentials into addon settings.

## Supported Actions
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

## Data and Storage

### Settings
Settings are in `resources/settings.xml`.
Key groups:
- Account slots 1..3 (`account{n}_enabled`, `account{n}_url`, `account{n}_username`, `account{n}_password`, `account{n}_name`)
- Library settings (`library_path`, `library_source_created`, etc.)
- Playback/UI settings (`show_hidden`)

### Overrides JSON
- File path: addon profile `overrides.json`
- Accessed via `load_overrides()` and `save_overrides()` in `torbox_common.py`
- Typical entry shape:
  - `title`
  - `year` (optional)
  - `type` (`tvshow` or `movie`)
  - `tvdb_id` (optional)
  - `tmdb_id` (optional)
  - `subs` (optional list)

### Subtitle Metadata
Subtitle selections are persisted under each override entry in `subs`, allowing repeat use and auditability.

## Library Export Behavior
- Movies:
  - Chooses largest direct video file in folder as main feature.
  - Writes `movie.nfo` only when TMDB ID exists.
  - Writes one STRM per movie.
- TV shows:
  - Recursively walks folders and extracts episode numbers from file names.
  - Writes `tvshow.nfo` only when TVDB ID exists.
  - Writes per-episode STRM files.
- First export:
  - Adds source to Kodi `sources.xml` as `TorBox Library`.
- Later exports:
  - Triggers `UpdateLibrary(video)`.

## Setup Server and Phone Flow
- HTTP server runs on `0.0.0.0:8765`.
- `QRDialog` displays QR code URL to access setup form on phone.
- Form posts URL/username/password.
- Server validates payload and saves credentials.
- Setup templates are centralized in `torbox_text.py`.
- Existing URL/username are prefilled in the form.
- Prefill values are HTML-escaped before injection.

## UI/Message Conventions
- User-facing strings are centralized in `torbox_text.py`.
- Keep new user-facing text in `torbox_text.py` to simplify localization and consistency.
- Keep runtime labels/notifications aligned with `APP_NAME` from `torbox_common.py`.

## Robustness and Safety Improvements Already Applied
- Guarded account query parsing in router.
- Hardened WebDAV XML parsing (missing fields, bad sizes, empty href/text).
- Fallback behavior when stream URL cannot be safely converted to authenticated form.
- Setup server lifecycle cleanup when reopened/closed.
- Setup form validation for missing fields.
- Reduced setup server log noise by overriding BaseHTTPRequestHandler log method.

## Known Environment Caveat
When editing outside Kodi runtime, static analysis often reports unresolved imports for:
- `xbmc`
- `xbmcgui`
- `xbmcplugin`
- `xbmcvfs`
This is expected in normal editor environments and not necessarily a runtime issue in Kodi.

## Important Files to Read First in Future Sessions
1. `addon.py`
2. `torbox_common.py`
3. `torbox_text.py`
4. `torbox_setup.py`
5. `torbox_library.py`
6. `torbox_webdav.py`
7. `torbox_subtitles.py`

## Practical Next Enhancements
- Add explicit module-level tests outside Kodi for pure functions (name parsing, episode extraction, overrides handling).
- Add optional localization key mapping strategy for all constants in `torbox_text.py`.
- Add structured log levels and event markers for easier troubleshooting.
- Add user-visible validation hints for malformed WebDAV URL format before submission.
- Optional: support multiple subtitle languages and language preference setting.

## Maintenance Rules
- Keep `addon.py` focused on routing/UI orchestration.
- Keep shared cross-cutting logic in `torbox_common.py`.
- Keep all UI text/templates in `torbox_text.py`.
- Avoid hardcoding user-facing text in feature modules.
- Preserve compatibility with Kodi plugin query action scheme.
