"""Automatic movie/series identification for TorBox folders (Infuse/VidHub style).

For every top-level folder of an account we read the release name ("The.Bear.S03.1080p.WEB"),
decide whether it's a movie or a series, search TMDB and keep the result only when the title
is a close match. Matches are stored in overrides.json with "source": "auto". Entries without
that marker were set by hand (context menu "Set show title/override") and are never touched.
"""

import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from urllib.parse import unquote, urlencode

import xbmc
import xbmcgui

from torbox_common import (
    APP_NAME,
    VIDEO_EXTS,
    _QUALITY_TAGS,
    extract_episode_info,
    get_account,
    get_tmdb_key,
    load_overrides,
    log,
    save_overrides,
)
from torbox_http import fetch_json
from torbox_text import (
    DIALOG_IDENTIFY_DONE,
    DIALOG_IDENTIFY_MODE,
    DIALOG_IDENTIFY_MODE_ALL,
    DIALOG_IDENTIFY_MODE_NEW,
    DIALOG_IDENTIFY_NOTHING,
    DIALOG_IDENTIFY_UNMATCHED,
    NOTIFY_ACCOUNT_NOT_FOUND,
    PROGRESS_IDENTIFY,
)
from torbox_webdav import parse_propfind, propfind

SOURCE_AUTO = 'auto'
TMDB_API = 'https://api.themoviedb.org/3'
POSTER_BASE = 'https://image.tmdb.org/t/p/w500'
MIN_SCORE = 0.8
WORKERS = 4

# --- release name parsing ----------------------------------------------------------

_EXT_RE = re.compile(r'\.({})$'.format('|'.join(e.lstrip('.') for e in VIDEO_EXTS)), re.IGNORECASE)
_LEADING_TAGS_RE = re.compile(r'^\s*(?:\[[^\]]*\]\s*|\{[^}]*\}\s*)+')
_YEAR_RE = re.compile(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)')
_TV_RE = re.compile(
    r'\bS\d{1,2}(?:[ ._-]?E\d{1,3})?\b'
    r'|\b(?:Season|Temporada|Saison|Staffel)[ ._-]?\d{1,2}\b'
    r'|\b\d{1,2}x\d{2,3}\b'
    r'|\bComplete[ ._-](?:Series|Season)\b'
    r'|\bE(?:P)?\d{2,3}\b',
    re.IGNORECASE,
)
_SEASON_FOLDER_RE = re.compile(r'^(?:S\d{1,2}|Season[ ._-]?\d{1,2}|Temporada[ ._-]?\d{1,2})\b', re.IGNORECASE)
_BRACKET_RE = re.compile(r'[\[({]')


def parse_release_name(name):
    """Split a release/folder name into a search title, a year and a series hint.
    The title is only used to query TMDB; it is never shown in the UI."""
    value = _EXT_RE.sub('', name or '')
    value = _LEADING_TAGS_RE.sub('', value)
    if ' ' not in value or value.count('.') >= 2:
        value = re.sub(r'[._]+', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip()

    tv_match = _TV_RE.search(value)
    cuts = [len(value)]
    if tv_match and tv_match.start() > 0:
        cuts.append(tv_match.start())

    year = None
    for match in _YEAR_RE.finditer(value):
        if match.start() == 0:
            continue  # a title like "1917" or "2012"
        year = int(match.group(1))
        cuts.append(match.start())
        break

    for match in _QUALITY_TAGS.finditer(value):
        if match.start() > 0:
            cuts.append(match.start())
            break

    for match in _BRACKET_RE.finditer(value):
        if match.start() > 0:
            cuts.append(match.start())
            break

    title = value[:min(cuts)]
    title = re.sub(r'[\s\-–:(\[{]+$', '', title).strip()
    if not title:
        title = value
    return {'title': title, 'year': year, 'tv_hint': bool(tv_match)}


# --- movie or series ---------------------------------------------------------------

def _guess_type_from_contents(account, folder_path):
    """'tvshow' / 'movie' from a folder's files, or None when it can't be read."""
    root = propfind(account['url'] + folder_path, account['username'], account['password'], depth=1)
    if root is None:
        return None
    items = parse_propfind(root, account['url'], folder_path)

    if any(i['is_collection'] and _SEASON_FOLDER_RE.match(i['name']) for i in items):
        return 'tvshow'
    videos = [
        i for i in items
        if not i['is_collection']
        and os.path.splitext(i['name'])[1].lower() in VIDEO_EXTS
        and 'sample' not in i['name'].lower()
    ]
    numbered = [v for v in videos if extract_episode_info(v['name'])[0] is not None]
    if len(numbered) >= 2 or (len(videos) >= 3 and numbered):
        return 'tvshow'
    if videos:
        return 'movie'
    return None


# --- TMDB --------------------------------------------------------------------------

def _tmdb_get(path, params):
    key = get_tmdb_key(notify=False)
    if not key:
        raise ValueError('TMDB key not configured')
    url = '{}{}?{}'.format(TMDB_API, path, urlencode(params))
    return fetch_json(url, headers={'Accept': 'application/json', 'Authorization': 'Bearer {}'.format(key)}) or {}


def _normalize(text):
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace('&', ' and ')
    text = re.sub(r'[^a-z0-9]+', ' ', text).strip()
    return re.sub(r'^(?:the|a|an|el|la|los|las|le|les|der|die|das) ', '', text)


def _score(query, year, result, media_type):
    names = [result.get('title') or result.get('name'), result.get('original_title') or result.get('original_name')]
    q = _normalize(query)
    names = [n for n in names if n]
    similarity = max([SequenceMatcher(None, q, _normalize(n)).ratio() for n in names] or [0])
    # "Frieren" should match "Frieren: Beyond Journey's End"; slightly below an exact match
    # so "Dune" still prefers "Dune" over "Dune: Part Two".
    for name in names:
        if ':' in name:
            similarity = max(similarity, 0.95 * SequenceMatcher(None, q, _normalize(name.split(':')[0])).ratio())
    date = result.get('release_date') or result.get('first_air_date') or ''
    result_year = int(date[:4]) if date[:4].isdigit() else None
    bonus = 0.0
    if year and result_year:
        diff = abs(year - result_year)
        if diff == 0:
            bonus = 0.1
        elif diff == 1:
            bonus = 0.05
        else:
            # A series' folder year is often the season's year, not the premiere's.
            bonus = -0.05 if media_type == 'tvshow' else -0.2
    return similarity + bonus, similarity, result_year


def _search(media_type, title, year):
    """Best (score, result, year) for one media type, or None."""
    path = '/search/tv' if media_type == 'tvshow' else '/search/movie'
    params = {'query': title, 'include_adult': 'false'}
    if year:
        params['first_air_date_year' if media_type == 'tvshow' else 'year'] = year
    results = (_tmdb_get(path, params).get('results') or [])[:10]
    if not results and year:
        params.pop('first_air_date_year', None)
        params.pop('year', None)
        results = (_tmdb_get(path, params).get('results') or [])[:10]

    best = None
    for result in results:
        total, similarity, result_year = _score(title, year, result, media_type)
        if similarity < 0.7:
            continue
        if best is None or total > best[0]:
            best = (total, result, result_year)
    return best


def _build_entry(media_type, result, result_year):
    tmdb_id = str(result['id'])
    entry = {
        'title': result.get('title') or result.get('name'),
        'type': media_type,
        'tmdb_id': tmdb_id,
        'source': SOURCE_AUTO,
    }
    if result_year:
        entry['year'] = result_year
    if result.get('poster_path'):
        entry['thumb'] = POSTER_BASE + result['poster_path']
    if result.get('overview'):
        entry['plot'] = result['overview']
    try:
        ids = _tmdb_get('/{}/{}/external_ids'.format('tv' if media_type == 'tvshow' else 'movie', tmdb_id), {})
        if ids.get('imdb_id'):
            entry['imdb_id'] = ids['imdb_id']
        if media_type == 'tvshow' and ids.get('tvdb_id'):
            entry['tvdb_id'] = str(ids['tvdb_id'])
    except Exception as exc:
        log('identify: external ids failed for {}: {}'.format(tmdb_id, exc), xbmc.LOGWARNING)
    return entry


def identify_folder(account, raw_name, folder_path):
    """Return an override entry for one folder, or None when nothing matched well enough."""
    parsed = parse_release_name(raw_name)
    if parsed['tv_hint']:
        types = ['tvshow']
    else:
        guessed = _guess_type_from_contents(account, folder_path)
        types = [guessed] if guessed else ['movie', 'tvshow']

    # Fallback queries for names that join two titles, e.g. "Frieren - Sousou no Frieren".
    queries = [parsed['title']]
    queries += [part.strip() for part in re.split(r'\s+-\s+|\s*/\s*', parsed['title']) if part.strip()][:3]

    best = None
    for query in dict.fromkeys(queries):
        for media_type in types:
            found = _search(media_type, query, parsed['year'])
            if found and (best is None or found[0] > best[0]):
                best = found + (media_type,)
        if best is not None and best[0] >= MIN_SCORE:
            break

    if best is None or best[0] < MIN_SCORE:
        log('identify: no match for "{}" (searched "{}" {} as {})'.format(
            raw_name, parsed['title'], parsed['year'], '/'.join(types)))
        return None

    score, result, result_year, media_type = best
    entry = _build_entry(media_type, result, result_year)
    log('identify: "{}" -> {} "{}" ({}) score {:.2f}'.format(
        raw_name, media_type, entry['title'], entry.get('year'), score))
    return entry


# --- applying matches --------------------------------------------------------------

def is_manual(entry):
    return bool(entry) and bool(entry.get('title')) and entry.get('source') != SOURCE_AUTO


def _merge_and_save(matches):
    """Write auto matches without clobbering manual overrides or kept per-folder data."""
    latest = load_overrides()
    for raw_name, entry in matches.items():
        existing = latest.get(raw_name, {})
        if is_manual(existing):
            continue
        for keep in ('subs', 'season', 'force_season'):
            if existing.get(keep) is not None:
                entry[keep] = existing[keep]
        latest[raw_name] = entry
    save_overrides(latest)
    return latest


def _folder_path(item):
    path = unquote(item.get('path', ''))
    return path if path.endswith('/') else path + '/'


def identify_items(account, items, progress=None):
    """Identify the given root folders in parallel. Returns ({raw_name: entry}, [unmatched names])."""
    matches, unmatched = {}, []
    total = len(items)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(identify_folder, account, item['name'], _folder_path(item)): item['name']
                   for item in items}
        for done, future in enumerate(as_completed(futures), 1):
            name = futures[future]
            try:
                entry = future.result()
            except Exception as exc:
                log('identify: failed for "{}": {}'.format(name, exc), xbmc.LOGWARNING)
                entry = None
            if entry:
                matches[name] = entry
            else:
                unmatched.append(name)
            if progress is not None:
                progress.update(int(done * 100 / max(total, 1)), PROGRESS_IDENTIFY.format(done, total, name[:60]))
                if progress.iscanceled():
                    for pending in futures:
                        pending.cancel()
                    break
    if matches:
        _merge_and_save(matches)
    return matches, unmatched


def root_folders(account):
    root = propfind(account['url'] + '/', account['username'], account['password'], depth=1)
    if root is None:
        return None
    return [i for i in parse_propfind(root, account['url'], '/')
            if i.get('is_collection') and i.get('name') and not i['name'].startswith('.')]


def pending_folders(folders, overrides, redo_auto=False):
    """Folders that still need identifying (never ones with a manual override)."""
    pending = []
    for item in folders:
        entry = overrides.get(item['name'], {})
        if is_manual(entry):
            continue
        if entry.get('title') and not redo_auto:
            continue
        pending.append(item)
    return pending


def identify_library(account_index):
    """'Identify Library' button: match every folder of one account against TMDB."""
    account = get_account(account_index)
    if not account:
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_ACCOUNT_NOT_FOUND, xbmcgui.NOTIFICATION_ERROR)
        return

    dialog = xbmcgui.Dialog()
    mode = dialog.select(DIALOG_IDENTIFY_MODE.format(account['name']),
                         [DIALOG_IDENTIFY_MODE_NEW, DIALOG_IDENTIFY_MODE_ALL])
    if mode < 0:
        return

    folders = root_folders(account)
    if folders is None:
        return
    pending = pending_folders(folders, load_overrides(), redo_auto=(mode == 1))
    if not pending:
        dialog.ok(APP_NAME, DIALOG_IDENTIFY_NOTHING)
        return

    progress = xbmcgui.DialogProgress()
    progress.create(APP_NAME, PROGRESS_IDENTIFY.format(0, len(pending), ''))
    try:
        matches, unmatched = identify_items(account, pending, progress)
    finally:
        progress.close()

    movies = sum(1 for e in matches.values() if e['type'] == 'movie')
    message = DIALOG_IDENTIFY_DONE.format(len(matches), movies, len(matches) - movies, len(unmatched))
    if unmatched:
        message += DIALOG_IDENTIFY_UNMATCHED.format('\n'.join(sorted(unmatched)))
        dialog.textviewer(APP_NAME, message)
    else:
        dialog.ok(APP_NAME, message)
    xbmc.executebuiltin('Container.Refresh')


def identify_one(account, raw_name, folder_path):
    """Identify a single folder (export/download of an unidentified item). Returns the entry or None."""
    entry = identify_folder(account, raw_name, folder_path)
    if entry:
        _merge_and_save({raw_name: entry})
    return entry
