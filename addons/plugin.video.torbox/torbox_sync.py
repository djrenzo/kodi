"""Management > Push to Supabase: publish the whole TorBox catalog for the user addon.
Management > Fetch overrides from Supabase: merge the pushed overrides back into overrides.json.

What is pushed
  * overrides  - every overrides.json entry (auto and manual), raw entry included
  * titles     - one row per movie/show (folders of the same TMDB title share it), with
                 artwork, plot, ids, genres... from the overrides plus TMDB details
  * seasons / episodes - TMDB season and episode details for the shows' seasons on TorBox
  * subtitles  - the subtitles picked per folder (overrides 'subs')
  * media_files - every video file of every account, numbered the way the library export
                 numbers them (season overrides applied), with a ready-to-play authed URL
  * accounts, sync_runs

The local overrides.json is the source of truth: rows of folders that no longer have an
override are removed (after asking), files no longer on TorBox are removed for accounts
that could be listed completely. TMDB details are fetched only for new titles, titles
with new seasons and ones last fetched over TMDB_REFRESH_DAYS ago, unless asked to
refresh everything.
"""

import datetime
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote, urlparse

import xbmc
import xbmcgui
import xbmcvfs

from torbox_common import (
    APP_NAME,
    OVERRIDES_FILE,
    VIDEO_EXTS,
    extract_bare_episode,
    extract_episode_info,
    get_accounts,
    get_tmdb_key,
    guess_season,
    subfolder_season,
    load_overrides,
    log,
    save_overrides,
)
from torbox_identify import SOURCE_AUTO, _folder_path, _normalize, _tmdb_get, root_folders
from torbox_srt import adjustments_of
from torbox_supabase import SupabaseClient, SupabaseError, is_configured
from torbox_text import (
    DIALOG_SUPABASE_DELETE_OVERRIDES,
    DIALOG_SUPABASE_DONE,
    DIALOG_SUPABASE_EMPTY_OVERRIDES,
    DIALOG_SUPABASE_FAILED,
    DIALOG_SUPABASE_FETCH_CONFIRM,
    DIALOG_SUPABASE_FETCH_DONE,
    DIALOG_SUPABASE_FETCH_EMPTY,
    DIALOG_SUPABASE_FETCH_FAILED,
    DIALOG_SUPABASE_FETCH_REPLACE,
    DIALOG_SUPABASE_FETCH_UP_TO_DATE,
    DIALOG_SUPABASE_MODE,
    DIALOG_SUPABASE_MODE_CHANGED,
    DIALOG_SUPABASE_MODE_REFRESH,
    DIALOG_SUPABASE_NOT_ADMIN,
    DIALOG_SUPABASE_RUN_MIGRATIONS,
    DIALOG_SUPABASE_NOT_CONFIGURED,
    DIALOG_SUPABASE_UNREACHABLE,
    NOTIFY_NO_ACCOUNTS,
    NOTIFY_SUPABASE_CANCELLED,
    PROGRESS_SUPABASE_FETCH,
    PROGRESS_SUPABASE_LIST,
    PROGRESS_SUPABASE_LOGIN,
    PROGRESS_SUPABASE_TMDB,
    PROGRESS_SUPABASE_UPLOAD,
)
from torbox_webdav import build_authed_url, parse_propfind, propfind

WORKERS = 4
TMDB_REFRESH_DAYS = 30
TMDB_IMAGE = 'https://image.tmdb.org/t/p/{}{}'
TMDB_MAX_SEASON_APPENDS = 19  # TMDB allows 20 append_to_response items; one is external_ids
MEDIA_TYPES = ('movie', 'tvshow')
SUB_LANGUAGES = {'sp': 'es'}  # the subtitle dialog's 'sp' option is Spanish too


class _Cancelled(Exception):
    pass


# --- small value helpers -----------------------------------------------------------

def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def _text(value):
    value = '' if value is None else str(value).strip()
    return value or None


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _date(value):
    value = _text(value)
    return value[:10] if value and len(value) >= 10 else None


def _image(path, size):
    return TMDB_IMAGE.format(size, path) if path else None


def _rating(value):
    try:
        return round(float(value), 2) if value else None
    except (TypeError, ValueError):
        return None


def _media_type(entry):
    value = entry.get('type') or 'tvshow'
    return value if value in MEDIA_TYPES else None


def title_key(entry):
    """Identity of the movie/show an override points at: its TMDB id (or TVDB/IMDb id,
    or failing all ids, its normalized title and year) plus the media type."""
    media_type = _media_type(entry) or 'tvshow'
    for field in ('tmdb_id', 'tvdb_id', 'imdb_id'):
        value = _text(entry.get(field))
        if value:
            return '{}:{}:{}'.format(media_type, field[:-3], value)
    return '{}:title:{}:{}'.format(media_type, _normalize(entry.get('title')), _int(entry.get('year')) or '')


def _progress(progress, percent, message):
    progress.update(max(0, min(100, int(percent))), message)
    if progress.iscanceled():
        raise _Cancelled()


# --- TorBox listing ----------------------------------------------------------------

def _walk(account, remote_path):
    """(video items under a folder, whether every subfolder could be listed)."""
    xml_root = propfind(account['url'] + remote_path, account['username'], account['password'], depth=1)
    if xml_root is None:
        return [], False

    files, complete = [], True
    for item in parse_propfind(xml_root, account['url'], remote_path):
        if item['is_collection']:
            child = unquote(item['path'])
            sub_files, sub_complete = _walk(account, child if child.endswith('/') else child + '/')
            files.extend(sub_files)
            complete = complete and sub_complete
        elif (os.path.splitext(item['name'])[1].lower() in VIDEO_EXTS
              and 'sample' not in item['name'].lower()):
            files.append(item)
    return files, complete


def _list_account(account, progress, start, span):
    """({root folder name: [video items]}, complete) for one account."""
    folders = root_folders(account)
    if folders is None:
        return {}, False

    listing, complete = {}, True
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(_walk, account, _folder_path(folder)): folder['name'] for folder in folders}
        try:
            for done, future in enumerate(as_completed(futures), 1):
                name = futures[future]
                try:
                    items, ok = future.result()
                except Exception as exc:
                    log('Supabase push: listing "{}" failed: {}'.format(name, exc), xbmc.LOGWARNING)
                    items, ok = [], False
                listing[name] = items
                complete = complete and ok
                _progress(progress, start + span * done / max(len(futures), 1),
                          PROGRESS_SUPABASE_LIST.format(account['name'], done, len(futures)))
        except _Cancelled:
            for future in futures:
                future.cancel()
            raise
    return listing, complete


def number_files(raw_name, override, items):
    """[(item, season, episode, is_main)], numbered like the library export does: a forced
    season replaces the file's season, files with only an episode number take the season of
    their subfolder, else the season override or the season in the folder name. Movies: the
    largest file is the main one."""
    if _media_type(override) == 'movie' and override.get('title'):
        main = max(items, key=lambda item: item['size']) if items else None
        return [(item, None, None, item is main) for item in items]

    season_override = _int(override.get('season'))
    forced = season_override if override.get('force_season') else None
    numbered = []
    for item in items:
        season, episode = extract_episode_info(item['name'])
        if season is not None:
            if forced is not None:
                season = forced
        else:
            episode = extract_bare_episode(item['name'])
            if episode is not None:
                season = forced if forced is not None else subfolder_season(item, raw_name)
                if season is None:
                    season = season_override if season_override is not None else guess_season(raw_name)
        numbered.append((item, season, episode, False))
    return numbered


# --- TMDB details ------------------------------------------------------------------

def _fetch_tmdb(media_type, tmdb_id, seasons):
    """(details, {season: [episodes]}) from TMDB; season details only for the given seasons."""
    kind = 'tv' if media_type == 'tvshow' else 'movie'
    wanted = sorted(seasons) if media_type == 'tvshow' else []
    chunks = [wanted[i:i + TMDB_MAX_SEASON_APPENDS] for i in range(0, len(wanted), TMDB_MAX_SEASON_APPENDS)] or [[]]

    details, episodes = None, {}
    for chunk in chunks:
        append = ['external_ids'] + ['season/{}'.format(season) for season in chunk]
        data = _tmdb_get('/{}/{}'.format(kind, tmdb_id), {'append_to_response': ','.join(append)})
        if not data.get('id'):
            raise ValueError('TMDB has no {} {}'.format(kind, tmdb_id))
        details = details or data
        for season in chunk:
            season_data = data.get('season/{}'.format(season)) or {}
            if season_data.get('episodes') is not None:
                episodes[season] = season_data['episodes']
    return details, episodes


def _enriched(row, details, episodes, previous_seasons, synced_at):
    """The title row completed with TMDB details. Values from the override win."""
    is_tv = row['media_type'] == 'tvshow'
    ids = details.get('external_ids') or {}
    premiered = _date(details.get('first_air_date' if is_tv else 'release_date'))
    runtime = (details.get('episode_run_time') or [None])[0] if is_tv else details.get('runtime')

    row = dict(row)
    row.update({
        'original_title': _text(details.get('original_name' if is_tv else 'original_title')),
        'tagline': _text(details.get('tagline')),
        'fanart_url': _image(details.get('backdrop_path'), 'w1280'),
        'genres': [genre['name'] for genre in details.get('genres') or [] if genre.get('name')],
        'rating': _rating(details.get('vote_average')),
        'premiered': premiered,
        'runtime': _int(runtime),
        'status': _text(details.get('status')),
        'episode_seasons': sorted(set(previous_seasons) | set(episodes)),
        'tmdb_synced_at': synced_at,
    })
    defaults = {
        'poster_url': _image(details.get('poster_path'), 'w500'),
        'plot': _text(details.get('overview')),
        'year': _int(premiered[:4]) if premiered else None,
        'imdb_id': _text(ids.get('imdb_id')),
        'tvdb_id': _text(ids.get('tvdb_id')) if is_tv else None,
    }
    for field, value in defaults.items():
        if not row.get(field):
            row[field] = value
    return row


def _season_rows(title_id, details):
    return [
        {
            'title_id': title_id,
            'season_number': season['season_number'],
            'name': _text(season.get('name')),
            'overview': _text(season.get('overview')),
            'poster_url': _image(season.get('poster_path'), 'w500'),
            'air_date': _date(season.get('air_date')),
            'episode_count': _int(season.get('episode_count')),
        }
        for season in details.get('seasons') or []
        if _int(season.get('season_number')) is not None
    ]


def _episode_rows(title_id, episodes):
    rows = []
    for season, items in episodes.items():
        for episode in items:
            number = _int(episode.get('episode_number'))
            if number is None:
                continue
            rows.append({
                'title_id': title_id,
                'season_number': _int(episode.get('season_number')) if episode.get('season_number') is not None else season,
                'episode_number': number,
                'name': _text(episode.get('name')),
                'overview': _text(episode.get('overview')),
                'still_url': _image(episode.get('still_path'), 'w300'),
                'air_date': _date(episode.get('air_date')),
                'runtime': _int(episode.get('runtime')),
                'rating': _rating(episode.get('vote_average')),
            })
    return rows


def _needs_tmdb(row, remote, seasons, refresh_all):
    if not row.get('tmdb_id'):
        return False
    if refresh_all or not remote or not remote.get('tmdb_synced_at'):
        return True
    if not set(seasons) <= set(remote.get('episode_seasons') or []):
        return True
    try:
        synced = datetime.date.fromisoformat(remote['tmdb_synced_at'][:10])
    except ValueError:
        return True
    return (datetime.date.today() - synced).days >= TMDB_REFRESH_DAYS


# --- building the rows -------------------------------------------------------------

def _title_rows(overrides):
    """({key: base title row}, {folder name: key}) from the identified overrides. When
    several folders point at one title, manual overrides win and gaps are filled in."""
    rows, folder_keys = {}, {}
    ordered = sorted(overrides.items(), key=lambda pair: pair[1].get('source') == SOURCE_AUTO)
    for folder_name, entry in ordered:
        if not entry.get('title') or not _media_type(entry):
            continue
        key = title_key(entry)
        folder_keys[folder_name] = key
        candidate = {
            'key': key,
            'media_type': _media_type(entry),
            'title': entry['title'],
            'year': _int(entry.get('year')),
            'tmdb_id': _text(entry.get('tmdb_id')),
            'tvdb_id': _text(entry.get('tvdb_id')),
            'imdb_id': _text(entry.get('imdb_id')),
            'plot': _text(entry.get('plot')),
            'poster_url': _text(entry.get('thumb')),
        }
        row = rows.setdefault(key, candidate)
        for field, value in candidate.items():
            if row.get(field) is None:
                row[field] = value
    for row in rows.values():
        # Columns left out keep what is stored (e.g. the TMDB plot when the override has none).
        for field in [f for f, v in row.items() if v is None]:
            del row[field]
    return rows, folder_keys


def _override_row(folder_name, entry, title_id, synced_at):
    return {
        'folder_name': folder_name,
        'title_id': title_id,
        'source': 'auto' if entry.get('source') == SOURCE_AUTO else 'manual',
        'media_type': _media_type(entry),
        'title': _text(entry.get('title')),
        'year': _int(entry.get('year')),
        'tmdb_id': _text(entry.get('tmdb_id')),
        'tvdb_id': _text(entry.get('tvdb_id')),
        'imdb_id': _text(entry.get('imdb_id')),
        'thumb_url': _text(entry.get('thumb')),
        'plot': _text(entry.get('plot')),
        'season': _int(entry.get('season')),
        'force_season': bool(entry.get('force_season')) and _int(entry.get('season')) is not None,
        'raw': entry,
        'synced_at': synced_at,
    }


def _subtitle_rows(folder_name, entry, title_id, synced_at):
    rows = []
    is_tv = _media_type(entry) == 'tvshow'
    for sub in entry.get('subs') or []:
        url, file_name = _text(sub.get('url')), _text(sub.get('fileName'))
        if not url or not file_name:
            continue
        season, episode = extract_episode_info(file_name) if is_tv else (None, None)
        language = _text(sub.get('language')) or 'en'
        try:
            adjustments = adjustments_of(sub)
        except (TypeError, ValueError):
            log('Supabase push: ignoring invalid subtitle adjustments of {}'.format(file_name), xbmc.LOGWARNING)
            adjustments = {}
        rows.append({
            'folder_name': folder_name,
            'title_id': title_id,
            'season_number': season,
            'episode_number': episode,
            'language': SUB_LANGUAGES.get(language, language),
            'hearing_impaired': bool(sub.get('hi')),
            'file_name': file_name,
            'url': url,
            'fps_from': adjustments.get('fps_from'),
            'fps_to': adjustments.get('fps_to'),
            'shift_ms': adjustments.get('shift_ms'),
            'synced_at': synced_at,
        })
    return rows


def _file_row(account, folder_name, title_id, numbered, seen_at):
    item, season, episode, is_main = numbered
    return {
        'account_id': account['index'],
        'folder_name': folder_name,
        'title_id': title_id,
        'remote_path': unquote(urlparse(item['full_url']).path),
        'file_name': item['name'],
        'size_bytes': int(item.get('size') or 0),
        'season_number': season,
        'episode_number': episode,
        'is_main': is_main,
        'webdav_url': item['full_url'],
        'stream_url': build_authed_url(item['full_url'], account['username'], account['password']),
        'last_seen_at': seen_at,
    }


# --- the push ----------------------------------------------------------------------

def _enrich_titles(title_rows, remote_titles, seasons_by_key, refresh_all, synced_at, progress):
    """TMDB details for the titles that need them: ({key: enriched row}, {key: (details, episodes)})."""
    if not get_tmdb_key(notify=False):
        log('Supabase push: no TMDB key configured, skipping TMDB details', xbmc.LOGWARNING)
        return {}, {}

    todo = [key for key, row in title_rows.items()
            if _needs_tmdb(row, remote_titles.get(key), seasons_by_key.get(key, set()), refresh_all)]
    enriched, fetched = {}, {}
    if not todo:
        return enriched, fetched

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {
            pool.submit(_fetch_tmdb, title_rows[key]['media_type'], title_rows[key]['tmdb_id'],
                        seasons_by_key.get(key, set())): key
            for key in todo
        }
        try:
            for done, future in enumerate(as_completed(futures), 1):
                key = futures[future]
                try:
                    details, episodes = future.result()
                except Exception as exc:
                    log('Supabase push: TMDB details for {} failed: {}'.format(key, exc), xbmc.LOGWARNING)
                else:
                    previous = (remote_titles.get(key) or {}).get('episode_seasons') or []
                    enriched[key] = _enriched(title_rows[key], details, episodes, previous, synced_at)
                    fetched[key] = (details, episodes)
                _progress(progress, 55 + 25 * done / len(futures),
                          PROGRESS_SUPABASE_TMDB.format(done, len(futures)))
        except _Cancelled:
            for future in futures:
                future.cancel()
            raise
    return enriched, fetched


def _push(client, refresh_all, progress):
    run_started = _now_iso()
    stats = {}

    overrides = load_overrides()
    accounts = get_accounts()

    # Overrides that exist in Supabase but not locally any more.
    remote_folders = {row['folder_name'] for row in client.select_all('overrides', 'folder_name', 'folder_name')}
    stale_overrides = sorted(remote_folders - set(overrides))
    delete_overrides = True
    if stale_overrides:
        preview = '\n'.join(name[:70] for name in stale_overrides[:10])
        if len(stale_overrides) > 10:
            preview += '\n...'
        delete_overrides = xbmcgui.Dialog().yesno(
            APP_NAME, DIALOG_SUPABASE_DELETE_OVERRIDES.format(len(stale_overrides), preview))

    # 1. Every video file on TorBox.
    listings, unreachable = {}, []
    for position, account in enumerate(accounts):
        span = 50.0 / len(accounts)
        listing, complete = _list_account(account, progress, 5 + position * span, span)
        listings[account['index']] = (listing, complete)
        if not complete:
            unreachable.append(account['name'])

    title_rows, folder_keys = _title_rows(overrides)
    numbered_files = []  # (account, folder name, numbered file)
    seasons_by_key = {}
    for account in accounts:
        listing, _ = listings[account['index']]
        for folder_name, items in listing.items():
            override = overrides.get(folder_name, {})
            key = folder_keys.get(folder_name)
            for numbered in number_files(folder_name, override, items):
                numbered_files.append((account, folder_name, numbered))
                if key and numbered[1] is not None:
                    seasons_by_key.setdefault(key, set()).add(numbered[1])

    # 2. TMDB details.
    remote_titles = {row['key']: row for row in
                     client.select_all('titles', 'key,tmdb_synced_at,episode_seasons', 'key')}
    enriched, fetched = _enrich_titles(title_rows, remote_titles, seasons_by_key, refresh_all,
                                       run_started, progress)
    stats['tmdb_fetched'] = len(enriched)

    # 3. Upload.
    _progress(progress, 80, PROGRESS_SUPABASE_UPLOAD.format('titles'))
    run = client.insert('sync_runs', {'started_at': run_started}, returning='id')

    client.upsert('accounts', [
        {'id': account['index'], 'name': account['name'], 'webdav_url': account['url'],
         'username': account['username']}
        for account in accounts
    ], on_conflict='id')

    rows = [enriched.get(key, row) for key, row in title_rows.items()]
    title_ids = {row['key']: row['id'] for row in client.upsert('titles', rows, on_conflict='key', returning='id,key')}
    stats['titles'] = len(title_ids)

    _progress(progress, 84, PROGRESS_SUPABASE_UPLOAD.format('seasons and episodes'))
    season_rows, episode_rows = [], []
    for key, (details, episodes) in fetched.items():
        if title_rows[key]['media_type'] == 'tvshow' and key in title_ids:
            season_rows.extend(_season_rows(title_ids[key], details))
            episode_rows.extend(_episode_rows(title_ids[key], episodes))
    client.upsert('seasons', season_rows, on_conflict='title_id,season_number')
    client.upsert('episodes', episode_rows, on_conflict='title_id,season_number,episode_number')
    stats['seasons'], stats['episodes'] = len(season_rows), len(episode_rows)

    _progress(progress, 88, PROGRESS_SUPABASE_UPLOAD.format('overrides and subtitles'))
    override_rows, subtitle_rows = [], []
    for folder_name, entry in overrides.items():
        title_id = title_ids.get(folder_keys.get(folder_name))
        override_rows.append(_override_row(folder_name, entry, title_id, run_started))
        subtitle_rows.extend(_subtitle_rows(folder_name, entry, title_id, run_started))
    client.upsert('overrides', override_rows, on_conflict='folder_name')
    client.upsert('subtitles', subtitle_rows, on_conflict='folder_name,url')
    stats['overrides'], stats['subtitles'] = len(override_rows), len(subtitle_rows)
    stats['overrides_deleted'] = 0
    if delete_overrides:
        if stale_overrides:
            stats['overrides_deleted'] = client.delete('overrides', synced_at='lt.' + run_started)
        # Only when every remote override was just pushed; otherwise kept ones would lose theirs.
        client.delete('subtitles', synced_at='lt.' + run_started)

    _progress(progress, 92, PROGRESS_SUPABASE_UPLOAD.format('files'))
    file_rows = [
        _file_row(account, folder_name, title_ids.get(folder_keys.get(folder_name)), numbered, run_started)
        for account, folder_name, numbered in numbered_files
    ]
    client.upsert('media_files', file_rows, on_conflict='account_id,remote_path')
    stats['files'] = len(file_rows)
    stats['files_deleted'] = 0
    for account in accounts:
        if listings[account['index']][1]:
            stats['files_deleted'] += client.delete(
                'media_files', account_id='eq.{}'.format(account['index']), last_seen_at='lt.' + run_started)

    _progress(progress, 97, PROGRESS_SUPABASE_UPLOAD.format('cleanup'))
    stats['titles_pruned'] = client.rpc('prune_orphan_titles') or 0
    stats['unidentified_folders'] = sum(
        1 for account in accounts for name in listings[account['index']][0] if name not in folder_keys)
    stats['incomplete_accounts'] = unreachable

    client.update('sync_runs', {'finished_at': _now_iso(), 'stats': stats}, id='eq.{}'.format(run['id']))
    return stats


def push_to_supabase():
    dialog = xbmcgui.Dialog()
    if not is_configured():
        dialog.ok(APP_NAME, DIALOG_SUPABASE_NOT_CONFIGURED)
        return

    overrides = load_overrides()
    if not overrides:
        # Never mirror an empty file: that would wipe the catalog (e.g. on a fresh install).
        dialog.ok(APP_NAME, DIALOG_SUPABASE_EMPTY_OVERRIDES)
        return
    if not get_accounts():
        dialog.notification(APP_NAME, NOTIFY_NO_ACCOUNTS, xbmcgui.NOTIFICATION_ERROR)
        return

    mode = dialog.select(DIALOG_SUPABASE_MODE, [DIALOG_SUPABASE_MODE_CHANGED, DIALOG_SUPABASE_MODE_REFRESH])
    if mode < 0:
        return

    progress = xbmcgui.DialogProgress()
    progress.create(APP_NAME, PROGRESS_SUPABASE_LOGIN)
    try:
        client = SupabaseClient()
        client.login()
        if client.rpc('is_admin') is not True:
            progress.close()
            dialog.ok(APP_NAME, DIALOG_SUPABASE_NOT_ADMIN.format(client.config['email']))
            return
        stats = _push(client, refresh_all=(mode == 1), progress=progress)
    except _Cancelled:
        progress.close()
        dialog.notification(APP_NAME, NOTIFY_SUPABASE_CANCELLED, xbmcgui.NOTIFICATION_WARNING)
        return
    except Exception as exc:
        progress.close()
        log('Supabase push failed: {}'.format(traceback.format_exc()), xbmc.LOGERROR)
        message = DIALOG_SUPABASE_FAILED.format(exc if isinstance(exc, SupabaseError)
                                                else '{}: {}'.format(type(exc).__name__, exc))
        if 'schema cache' in str(exc):  # PostgREST: a column/table the database doesn't have yet
            message += DIALOG_SUPABASE_RUN_MIGRATIONS
        dialog.ok(APP_NAME, message)
        return
    progress.close()

    log('Supabase push done: {}'.format(stats))
    message = DIALOG_SUPABASE_DONE.format(**stats)
    if stats['incomplete_accounts']:
        message += DIALOG_SUPABASE_UNREACHABLE.format(', '.join(stats['incomplete_accounts']))
    dialog.ok(APP_NAME, message)


# --- fetch -------------------------------------------------------------------------

BACKUP_FILE = OVERRIDES_FILE[:-len('.json')] + '.backup.json'


def merge_overrides(local, remote, replace_changed):
    """(merged, stats). Folders only in Supabase are added; folders that differ are
    replaced only if replace_changed; folders only present locally are always kept."""
    merged = dict(local)
    stats = {'added': 0, 'replaced': 0, 'kept': 0}
    for folder_name, entry in remote.items():
        if folder_name not in local:
            merged[folder_name] = entry
            stats['added'] += 1
        elif local[folder_name] != entry:
            if replace_changed:
                merged[folder_name] = entry
                stats['replaced'] += 1
            else:
                stats['kept'] += 1
    stats['kept'] += sum(1 for folder_name in local if folder_name not in remote)
    return merged, stats


def fetch_from_supabase():
    """Management > Fetch overrides from Supabase: restore or update overrides.json from
    the raw entries of the last push. Works with reader logins too (it only reads)."""
    dialog = xbmcgui.Dialog()
    if not is_configured():
        dialog.ok(APP_NAME, DIALOG_SUPABASE_NOT_CONFIGURED)
        return

    progress = xbmcgui.DialogProgress()
    progress.create(APP_NAME, PROGRESS_SUPABASE_LOGIN)
    try:
        client = SupabaseClient()
        client.login()
        progress.update(50, PROGRESS_SUPABASE_FETCH)
        rows = client.select_all('overrides', 'folder_name,raw', 'folder_name')
    except Exception as exc:
        progress.close()
        log('Supabase fetch failed: {}'.format(traceback.format_exc()), xbmc.LOGERROR)
        dialog.ok(APP_NAME, DIALOG_SUPABASE_FETCH_FAILED.format(exc if isinstance(exc, SupabaseError)
                                                                else '{}: {}'.format(type(exc).__name__, exc)))
        return
    progress.close()

    remote = {row['folder_name']: row['raw'] for row in rows if isinstance(row.get('raw'), dict)}
    if not remote:
        dialog.ok(APP_NAME, DIALOG_SUPABASE_FETCH_EMPTY)
        return

    local = load_overrides()
    new = [name for name in remote if name not in local]
    changed = sorted(name for name in remote if name in local and local[name] != remote[name])
    counts = {
        'total': len(remote),
        'new': len(new),
        'changed': len(changed),
        'same': len(remote) - len(new) - len(changed),
        'local_only': sum(1 for name in local if name not in remote),
    }
    if not new and not changed:
        dialog.ok(APP_NAME, DIALOG_SUPABASE_FETCH_UP_TO_DATE.format(**counts))
        return
    if not dialog.yesno(APP_NAME, DIALOG_SUPABASE_FETCH_CONFIRM.format(**counts)):
        return

    replace_changed = False
    if changed:
        preview = '\n'.join(name[:70] for name in changed[:8])
        if len(changed) > 8:
            preview += '\n...'
        replace_changed = dialog.yesno(APP_NAME, DIALOG_SUPABASE_FETCH_REPLACE.format(len(changed), preview))

    merged, stats = merge_overrides(local, remote, replace_changed)
    if stats['added'] == 0 and stats['replaced'] == 0:
        return
    if xbmcvfs.exists(OVERRIDES_FILE) and not xbmcvfs.copy(OVERRIDES_FILE, BACKUP_FILE):
        log('Supabase fetch: could not back up overrides.json', xbmc.LOGWARNING)
    save_overrides(merged)
    log('Supabase fetch done: {}'.format(stats))
    dialog.ok(APP_NAME, DIALOG_SUPABASE_FETCH_DONE.format(**stats))
