import json
import os
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl, unquote, urlparse

import xbmc
import xbmcgui
import xbmcvfs

from torbox_common import (
    ADDON,
    ADDON_ID,
    APP_NAME,
    PROFILE_PATH,
    SKIP_EXTS,
    VIDEO_EXTS,
    build_url,
    extract_bare_episode,
    extract_episode_info,
    get_account,
    get_accounts,
    guess_season,
    load_overrides,
    log,
    save_overrides,
)
from torbox_text import (
    DIALOG_ASK_SEASON,
    DIALOG_CLEANUP_CONFIRM,
    DIALOG_CLEANUP_DONE,
    DIALOG_CLEANUP_NOTHING,
    DIALOG_CLEANUP_UNREACHABLE,
    DIALOG_EXPORT_MODE,
    DIALOG_EXPORT_MODE_ALL,
    DIALOG_EXPORT_MODE_NEW,
    DIALOG_EXPORT_NOTHING_NEW,
    DIALOG_IDENTIFY_EXPORT_FAILED,
    DIALOG_LIBRARY_EXPORT_ALREADY,
    DIALOG_LIBRARY_EXPORT_DONE,
    DIALOG_LIBRARY_EXPORT_SKIPPED,
    DIALOG_LIBRARY_PATH_NOT_CONFIGURED,
    DIALOG_LIBRARY_SOURCE_ADDED,
    NOTIFY_ACCOUNT_NOT_FOUND,
    NOTIFY_NO_ACCOUNTS,
    PROGRESS_CLEANUP_ACCOUNT,
    PROGRESS_CLEANUP_LIBRARY,
    PROGRESS_CLEANUP_TITLE,
    PROGRESS_IDENTIFY,
)
from torbox_identify import identify_items, identify_one, parse_release_name, pending_folders
from torbox_webdav import parse_propfind, propfind


def ensure_video_source(name, path):
    sources_file = xbmcvfs.translatePath('special://profile/sources.xml')

    if not os.path.exists(sources_file):
        root = ET.Element('sources')
        ET.SubElement(root, 'video')
        ET.ElementTree(root).write(sources_file, encoding='utf-8', xml_declaration=True)

    tree = ET.parse(sources_file)
    root = tree.getroot()

    video = root.find('video')
    if video is None:
        video = ET.SubElement(root, 'video')

    for source in video.findall('source'):
        source_name = source.find('name')
        if source_name is not None and source_name.text == name:
            return

    source = ET.SubElement(video, 'source')
    ET.SubElement(source, 'name').text = name

    path_el = ET.SubElement(source, 'path')
    path_el.set('pathversion', '1')
    path_el.text = path

    ET.SubElement(source, 'allowsharing').text = 'true'

    tree.write(sources_file, encoding='utf-8', xml_declaration=True)


def get_library_path():
    path = ADDON.getSettingString('library_path')
    if not path:
        xbmcgui.Dialog().notification(APP_NAME, DIALOG_LIBRARY_PATH_NOT_CONFIGURED, xbmcgui.NOTIFICATION_ERROR)
        return None
    return xbmcvfs.translatePath(path)


def join_path(base, *parts):
    """Join path parts, keeping '/' separators for Kodi VFS URLs such as smb://."""
    if '://' not in base:
        return os.path.join(base, *parts)

    path = base.rstrip('/')
    for part in parts:
        part = part.strip('/')
        if part:
            path = '{}/{}'.format(path, part)
    return path


def dir_exists(path):
    """xbmcvfs.exists only checks a directory when the path ends with a separator;
    without one it can report False for folders (SMB/NFS, Android storage)."""
    if not path:
        return False
    sep = '/' if '://' in path else os.sep
    return xbmcvfs.exists(path if path.endswith(('/', '\\')) else path + sep)


def write_text_file(path, content):
    folder = os.path.dirname(path)
    if not xbmcvfs.exists(folder):
        xbmcvfs.mkdirs(folder)

    with xbmcvfs.File(path, 'w') as fh:
        fh.write(content)


def write_tvshow_nfo(show_folder, title, tvdb_id=None, tmdb_id=None, imdb_id=None):
    if not tvdb_id and not tmdb_id:
        return

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tvshow>',
        '  <title>{}</title>'.format(title),
    ]
    if tvdb_id:
        xml.append('  <uniqueid type="tvdb" default="true">{}</uniqueid>'.format(tvdb_id))
    if tmdb_id:
        xml.append('  <uniqueid type="tmdb">{}</uniqueid>'.format(tmdb_id))
    if imdb_id:
        xml.append('  <uniqueid type="imdb">{}</uniqueid>'.format(imdb_id))
    xml.append('</tvshow>')

    write_text_file(join_path(show_folder, 'tvshow.nfo'), '\n'.join(xml))


def write_movie_nfo(movie_folder, title, year=None, tmdb_id=None, imdb_id=None):
    if not tmdb_id:
        return

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<movie>',
        '  <title>{}</title>'.format(title),
    ]
    if year:
        xml.append('  <year>{}</year>'.format(year))

    xml.append('  <uniqueid type="tmdb" default="true">{}</uniqueid>'.format(tmdb_id))

    if imdb_id:
        xml.append('  <uniqueid type="imdb">{}</uniqueid>'.format(imdb_id))
        
    xml.append('</movie>')

    write_text_file(join_path(movie_folder, 'movie.nfo'), '\n'.join(xml))


def get_media_library_root(library_root, media_type):
    if media_type == 'movie':
        return join_path(library_root, 'movies')
    return join_path(library_root, 'tvshows')


def walk_webdav(account, remote_path):
    xml_root = propfind(account['url'] + remote_path, account['username'], account['password'], depth=1)
    if xml_root is None:
        return []

    items = parse_propfind(xml_root, account['url'], remote_path)

    files = []
    for item in items:
        if item['is_collection']:
            child_path = unquote(item['path'])
            if not child_path.endswith('/'):
                child_path += '/'
            files.extend(walk_webdav(account, child_path))
            continue

        ext = os.path.splitext(item['name'])[1].lower()
        if ext in VIDEO_EXTS:
            files.append(item)

    return files


def find_main_video(account, remote_path):
    xml_root = propfind(account['url'] + remote_path, account['username'], account['password'], depth=1)
    if xml_root is None:
        return None

    items = parse_propfind(xml_root, account['url'], remote_path)
    videos = [
        item for item in items if not item['is_collection'] and os.path.splitext(item['name'])[1].lower() in VIDEO_EXTS
    ]

    if not videos:
        return None

    return max(videos, key=lambda item: item['size'])


def get_library_folder_for(folder_name):
    library_root = get_library_path()
    if not library_root or not ADDON.getSettingBool('library_source_created'):
        return None

    info = resolve_media_info(folder_name, load_overrides())
    media_root = get_media_library_root(library_root, info['media_type'])
    folder = join_path(media_root, library_folder_name(info))
    legacy = join_path(media_root, legacy_folder_name(info))
    if not dir_exists(folder) and dir_exists(legacy):
        return legacy  # exported before folders carried an id and not migrated yet
    return folder


def resolve_media_info(raw_name, overrides):
    """Return title/year/ids/type for a WebDAV folder from its (auto or manual) identification.
    Unidentified folders fall back to a title parsed from the release name, used only for
    file/folder naming (downloads), never for display."""
    override = overrides.get(raw_name, {})

    if override.get('title'):
        clean_title = override['title']
        year = override.get('year')
    else:
        parsed = parse_release_name(raw_name)
        clean_title, year = parsed['title'], parsed['year']

    return {
        'identified': bool(override.get('title')),
        'media_type': override.get('type', 'tvshow'),
        'title': clean_title,
        'year': year,
        'tvdb_id': override.get('tvdb_id'),
        'tmdb_id': override.get('tmdb_id'),
        'imdb_id': override.get('imdb_id'),
        'subs': override.get('subs', []),
    }


def movie_folder_name(title, year):
    return '{} ({})'.format(title, year) if year else title


_UNSAFE_CHARS = re.compile(r'[<>"/\\|?*]')


def library_folder_name(info):
    """'Title (Year) {tmdb-123}': the id keeps two titles with the same name apart, and
    Kodi's scrapers read it. Characters Windows/SMB can't store are replaced."""
    name = movie_folder_name(info['title'], info.get('year'))
    for key in ('tmdb', 'imdb', 'tvdb'):
        if info.get(key + '_id'):
            name = '{} {{{}-{}}}'.format(name, key, info[key + '_id'])
            break
    name = name.replace(':', ' -')
    return re.sub(r'\s+', ' ', _UNSAFE_CHARS.sub('', name)).strip(' .')


def legacy_folder_name(info):
    """Folder name used before ids were added (movies 'Title (Year)', shows 'Title')."""
    if info['media_type'] == 'movie':
        return movie_folder_name(info['title'], info.get('year'))
    return info['title']


def migrate_legacy_folder(media_root, info, rename_prefix=None):
    """Move an old-style folder to its id-based name, keeping subtitles and artwork in it.
    rename_prefix: (old, new) file name prefix; files named after the old folder (the movie
    STRM/video and its '<name>.es.srt', '<name>-poster.jpg' ...) are renamed to match.
    Returns the folder to use."""
    folder = join_path(media_root, library_folder_name(info))
    legacy = join_path(media_root, legacy_folder_name(info))
    if legacy == folder or dir_exists(folder) or not dir_exists(legacy):
        return folder
    if not xbmcvfs.rename(legacy, folder):
        log('Could not rename "{}" to "{}"'.format(legacy, folder), xbmc.LOGWARNING)
        return folder
    log('Renamed library folder "{}" -> "{}"'.format(legacy, folder))
    if rename_prefix and rename_prefix[0] != rename_prefix[1]:
        old, new = rename_prefix
        _, files = xbmcvfs.listdir(folder if folder.endswith('/') or '://' not in folder else folder + '/')
        for filename in files:
            if filename.startswith(old + '.') or filename.startswith(old + '-'):
                xbmcvfs.rename(join_path(folder, filename), join_path(folder, new + filename[len(old):]))
    return folder


def episode_basename(title, season, episode_no):
    return '{}.S{:02d}E{:02d}'.format(title, season, episode_no)


def _ask_season(raw_name, missing_count, overrides):
    """Season for episode files that only carry an episode number. Remembered per folder in
    the overrides so later exports don't ask again. Returns None if the user cancels."""
    override = overrides.get(raw_name, {})
    if override.get('season') is not None:
        return int(override['season'])

    default = guess_season(raw_name) or 1
    value = xbmcgui.Dialog().input(
        DIALOG_ASK_SEASON.format(missing_count, raw_name[:60]),
        defaultt=str(default),
        type=xbmcgui.INPUT_NUMERIC,
    )
    try:
        season = int(value)
    except (TypeError, ValueError):
        return None

    # Reload so we don't overwrite edits saved since the caller loaded its copy.
    latest = load_overrides()
    entry = latest.get(raw_name, {})
    entry['season'] = season
    latest[raw_name] = entry
    save_overrides(latest)
    overrides[raw_name] = entry
    return season


def numbered_episodes(raw_name, episodes, overrides):
    """Return [(item, season, episode_no)] for the files that can be numbered.
    Files with only an episode number (e.g. 'E02') get a season asked from the user."""
    numbered = []
    bare = []
    for item in episodes:
        season, episode_no = extract_episode_info(item['name'])
        if season is not None:
            numbered.append((item, season, episode_no))
            continue
        episode_no = extract_bare_episode(item['name'])
        if episode_no is not None:
            bare.append((item, episode_no))

    if bare:
        season = _ask_season(raw_name, len(bare), overrides)
        if season is None:
            log('No season given for {}; skipped {} episode(s)'.format(raw_name, len(bare)), xbmc.LOGWARNING)
        else:
            numbered.extend((item, season, episode_no) for item, episode_no in bare)

    return numbered


EXPORTS_FILE = os.path.join(PROFILE_PATH, 'exports.json')


def load_export_log():
    """{account index: {folder name: {identity, title, type, folder, files, time}}}"""
    if not xbmcvfs.exists(EXPORTS_FILE):
        return {}
    try:
        with xbmcvfs.File(EXPORTS_FILE, 'r') as f:
            return json.loads(f.read()) or {}
    except Exception as exc:
        log('Failed to load export log: {}'.format(exc), xbmc.LOGWARNING)
        return {}


def _save_export_log(data):
    if not xbmcvfs.exists(PROFILE_PATH):
        xbmcvfs.mkdirs(PROFILE_PATH)
    try:
        with xbmcvfs.File(EXPORTS_FILE, 'w') as f:
            f.write(json.dumps(data, indent=2))
    except Exception as exc:
        log('Failed to save export log: {}'.format(exc), xbmc.LOGWARNING)


def _identity(info):
    """What a folder was exported as; a different identity means it needs exporting again."""
    return '{}:{}:{}'.format(info['media_type'], info.get('tmdb_id') or info['title'],
                             library_folder_name(info))


def _mark_exported(account_index, raw_name, info, folder, files):
    data = load_export_log()
    data.setdefault(str(account_index), {})[raw_name] = {
        'identity': _identity(info),
        'title': info['title'],
        'type': info['media_type'],
        'folder': folder,
        'files': files,
        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    _save_export_log(data)


def export_status(export_log, account_index, raw_name, overrides):
    """None when the folder was exported under its current identification and its library
    folder still exists; otherwise the reason it needs exporting."""
    entry = export_log.get(str(account_index), {}).get(raw_name)
    if not entry:
        return 'not in export log'
    if not overrides.get(raw_name, {}).get('title'):
        return 'not identified'
    if entry.get('identity') != _identity(resolve_media_info(raw_name, overrides)):
        return 'identification changed'
    if not dir_exists(entry.get('folder')):
        return 'library folder missing'
    return None



def normalize_collection_path(child_path):
    normalized_path = unquote(child_path or '')
    if normalized_path and not normalized_path.endswith('/'):
        normalized_path += '/'
    return normalized_path


def _export_collection(account, account_index, raw_name, child_path, overrides, movies_root, tvshows_root):
    info = resolve_media_info(raw_name, overrides)
    media_type = info['media_type']
    clean_title = info['title']
    year = info['year']
    tvdb_id = info['tvdb_id']
    tmdb_id = info['tmdb_id']
    imdb_id = info['imdb_id']

    normalized_path = normalize_collection_path(child_path)
    if not normalized_path:
        return 0

    if media_type == 'movie':
        folder_name = library_folder_name(info)
        # Old export: its STRM and subtitles are named after the old folder; rename them too.
        movie_folder = migrate_legacy_folder(movies_root, info, (legacy_folder_name(info), folder_name))

        if not xbmcvfs.exists(movie_folder):
            xbmcvfs.mkdirs(movie_folder)

        write_movie_nfo(movie_folder, clean_title, year, tmdb_id, imdb_id)
        video_item = find_main_video(account, normalized_path)

        if video_item is None:
            log('No video found for movie: {}'.format(raw_name), xbmc.LOGWARNING)
            return 0

        strm_name = '{}.strm'.format(folder_name)
        strm_path = join_path(movie_folder, strm_name)
        plugin_url = build_url(
            {
                'action': 'play',
                'account': account_index,
                'url': video_item.get('full_url', ''),
                'strm': strm_path,
            }
        )
        write_text_file(strm_path, plugin_url)
        _mark_exported(account_index, raw_name, info, movie_folder, 1)
        return 1

    show_folder = migrate_legacy_folder(tvshows_root, info)
    if not xbmcvfs.exists(show_folder):
        xbmcvfs.mkdirs(show_folder)

    write_tvshow_nfo(show_folder, clean_title, tvdb_id, tmdb_id, imdb_id)

    created = 0
    for episode, season, episode_no in numbered_episodes(raw_name, walk_webdav(account, normalized_path), overrides):
        strm_name = '{}.strm'.format(episode_basename(clean_title, season, episode_no))
        strm_path = join_path(show_folder, strm_name)
        plugin_url = build_url(
            {
                'action': 'play',
                'account': account_index,
                'url': episode.get('full_url', ''),
                'strm': strm_path,
            }
        )
        write_text_file(strm_path, plugin_url)
        created += 1

    if created:
        _mark_exported(account_index, raw_name, info, show_folder, created)
    return created


def export_library(account_index):
    account = get_account(account_index)
    if not account:
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_ACCOUNT_NOT_FOUND, xbmcgui.NOTIFICATION_ERROR)
        return

    library_root = get_library_path()
    if not library_root:
        return

    mode = xbmcgui.Dialog().select(DIALOG_EXPORT_MODE.format(account['name']),
                                   [DIALOG_EXPORT_MODE_NEW, DIALOG_EXPORT_MODE_ALL])
    if mode < 0:
        return
    only_new = mode == 0

    if not xbmcvfs.exists(library_root):
        xbmcvfs.mkdirs(library_root)

    movies_root = get_media_library_root(library_root, 'movie')
    tvshows_root = get_media_library_root(library_root, 'tvshow')
    if not xbmcvfs.exists(movies_root):
        xbmcvfs.mkdirs(movies_root)
    if not xbmcvfs.exists(tvshows_root):
        xbmcvfs.mkdirs(tvshows_root)

    root_xml = propfind(account['url'] + '/', account['username'], account['password'], depth=1)
    if root_xml is None:
        return

    root_items = parse_propfind(root_xml, account['url'], '/')
    folders = [item for item in root_items if item.get('is_collection') and item.get('name')]

    already = 0
    if only_new:
        export_log = load_export_log()
        overrides = load_overrides()
        remaining = []
        reasons = {}
        for folder in folders:
            reason = export_status(export_log, account_index, folder['name'], overrides)
            if reason:
                remaining.append(folder)
                reasons[reason] = reasons.get(reason, 0) + 1
        already = len(folders) - len(remaining)
        log('Export (only new): {} already exported, to export: {}'.format(
            already, ', '.join('{} {}'.format(n, r) for r, n in sorted(reasons.items())) or 'none'))
        folders = remaining
        if not folders:
            xbmcgui.Dialog().ok(APP_NAME, DIALOG_EXPORT_NOTHING_NEW)
            return

    # Identify anything new first, so the library only gets proper TMDB names.
    pending = pending_folders(folders, load_overrides())
    if pending:
        progress = xbmcgui.DialogProgress()
        progress.create(APP_NAME, PROGRESS_IDENTIFY.format(0, len(pending), ''))
        try:
            identify_items(account, pending, progress)
        finally:
            progress.close()

    overrides = load_overrides()
    created = 0
    skipped = 0

    for root_item in folders:
        raw_name = root_item['name']
        if not overrides.get(raw_name, {}).get('title'):
            skipped += 1
            log('Export: skipping unidentified "{}"'.format(raw_name))
            continue

        created += _export_collection(
            account,
            account_index,
            raw_name,
            root_item.get('path', ''),
            overrides,
            movies_root,
            tvshows_root,
        )

    message = DIALOG_LIBRARY_EXPORT_DONE.format(created)
    if already:
        message += DIALOG_LIBRARY_EXPORT_ALREADY.format(already)
    if skipped:
        message += DIALOG_LIBRARY_EXPORT_SKIPPED.format(skipped)
    xbmcgui.Dialog().ok(APP_NAME, message)

    if not ADDON.getSettingBool('library_source_created'):
        ensure_video_source('TorBox Library', library_root)
        ADDON.setSettingBool('library_source_created', True)
        xbmcgui.Dialog().ok(
            APP_NAME,
            DIALOG_LIBRARY_SOURCE_ADDED,
        )
        xbmc.executebuiltin('ActivateWindow(Videos,Files,return)')
    else:
        xbmc.executebuiltin('UpdateLibrary(video)')


def export_library_item(account_index, folder_name, remote_path):
    account = get_account(account_index)
    if not account:
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_ACCOUNT_NOT_FOUND, xbmcgui.NOTIFICATION_ERROR)
        return

    library_root = get_library_path()
    if not library_root:
        return

    if not xbmcvfs.exists(library_root):
        xbmcvfs.mkdirs(library_root)

    movies_root = get_media_library_root(library_root, 'movie')
    tvshows_root = get_media_library_root(library_root, 'tvshow')
    if not xbmcvfs.exists(movies_root):
        xbmcvfs.mkdirs(movies_root)
    if not xbmcvfs.exists(tvshows_root):
        xbmcvfs.mkdirs(tvshows_root)

    overrides = load_overrides()
    if not overrides.get(folder_name, {}).get('title'):
        if not identify_one(account, folder_name, normalize_collection_path(remote_path)):
            xbmcgui.Dialog().ok(APP_NAME, DIALOG_IDENTIFY_EXPORT_FAILED.format(folder_name[:80]))
            return
        overrides = load_overrides()

    created = _export_collection(
        account,
        account_index,
        folder_name,
        remote_path,
        overrides,
        movies_root,
        tvshows_root,
    )
    xbmcgui.Dialog().ok(APP_NAME, DIALOG_LIBRARY_EXPORT_DONE.format(created))

    if not ADDON.getSettingBool('library_source_created'):
        ensure_video_source('TorBox Library', library_root)
        ADDON.setSettingBool('library_source_created', True)
        xbmcgui.Dialog().ok(
            APP_NAME,
            DIALOG_LIBRARY_SOURCE_ADDED,
        )
        xbmc.executebuiltin('ActivateWindow(Videos,Files,return)')
    else:
        xbmc.executebuiltin('UpdateLibrary(video)')


def _normalize_remote_path(url):
    return unquote(urlparse(url).path).rstrip('/')


def _collect_remote_paths(account, remote_path, found):
    """Recursively add every remote file path to found. Returns False if any listing failed,
    so a partial listing is never mistaken for missing content."""
    xml_root = propfind(account['url'] + remote_path, account['username'], account['password'], depth=1)
    if xml_root is None:
        return False

    for item in parse_propfind(xml_root, account['url'], remote_path):
        if item['is_collection']:
            child_path = unquote(item['path'])
            if not child_path.endswith('/'):
                child_path += '/'
            if not _collect_remote_paths(account, child_path, found):
                return False
        else:
            found.add(_normalize_remote_path(item['full_url']))

    return True


def _read_strm_target(strm_path):
    """Return (account_index, remote_path) for a STRM written by this addon's export, else None."""
    try:
        with xbmcvfs.File(strm_path) as fh:
            content = fh.read().strip()
    except Exception as exc:
        log('Could not read {}: {}'.format(strm_path, exc), xbmc.LOGWARNING)
        return None

    parsed = urlparse(content)
    if parsed.scheme != 'plugin' or parsed.netloc != ADDON_ID:
        return None

    params = dict(parse_qsl(parsed.query))
    if params.get('action') != 'play' or not params.get('url'):
        return None

    try:
        account_index = int(params.get('account', 1))
    except (TypeError, ValueError):
        return None

    return account_index, _normalize_remote_path(params['url'])


def _list_dir(path):
    dirs, files = xbmcvfs.listdir(path.rstrip('/') + '/')
    return dirs, files


def _remove_stale_strm(folder, strm_name):
    """Delete a STRM plus its companion files (subtitles, thumbs) sharing the same basename."""
    basename = os.path.splitext(strm_name)[0]
    xbmcvfs.delete(join_path(folder, strm_name))

    _, files = _list_dir(folder)
    for filename in files:
        if filename.startswith(basename + '.') and os.path.splitext(filename)[1].lower() in SKIP_EXTS:
            xbmcvfs.delete(join_path(folder, filename))


def _remove_folder_if_orphaned(folder):
    """Remove a title folder once no STRM remains, but only if it holds nothing but metadata."""
    dirs, files = _list_dir(folder)
    if dirs or any(os.path.splitext(filename)[1].lower() not in SKIP_EXTS for filename in files):
        return False

    for filename in files:
        xbmcvfs.delete(join_path(folder, filename))
    return xbmcvfs.rmdir(folder.rstrip('/') + '/')


def cleanup_library():
    library_root = get_library_path()
    if not library_root:
        return

    accounts = get_accounts()
    if not accounts:
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_NO_ACCOUNTS, xbmcgui.NOTIFICATION_ERROR)
        return

    progress = xbmcgui.DialogProgress()
    progress.create(PROGRESS_CLEANUP_TITLE.format(APP_NAME))

    available = {}
    unreachable = []
    stale = []
    try:
        for position, account in enumerate(accounts):
            if progress.iscanceled():
                return
            progress.update(int(position * 50 / len(accounts)), PROGRESS_CLEANUP_ACCOUNT.format(account['name']))

            found = set()
            if _collect_remote_paths(account, '/', found):
                available[account['index']] = found
            else:
                unreachable.append(account['name'])
                log('Cleanup: skipping account {} (listing failed)'.format(account['name']), xbmc.LOGWARNING)

        title_folders = []
        for media_type in ('movie', 'tvshow'):
            media_root = get_media_library_root(library_root, media_type)
            if xbmcvfs.exists(media_root.rstrip('/') + '/'):
                dirs, _ = _list_dir(media_root)
                title_folders.extend(join_path(media_root, name) for name in sorted(dirs))

        for position, folder in enumerate(title_folders):
            if progress.iscanceled():
                return
            progress.update(
                50 + int(position * 50 / max(1, len(title_folders))),
                PROGRESS_CLEANUP_LIBRARY.format(os.path.basename(folder)),
            )

            _, files = _list_dir(folder)
            for filename in files:
                if os.path.splitext(filename)[1].lower() != '.strm':
                    continue

                target = _read_strm_target(join_path(folder, filename))
                if target is None:
                    continue

                account_index, remote_path = target
                # Only judge STRMs whose account was listed completely; anything else is kept.
                if account_index in available and remote_path not in available[account_index]:
                    stale.append((folder, filename))
    finally:
        progress.close()

    if unreachable:
        xbmcgui.Dialog().ok(APP_NAME, DIALOG_CLEANUP_UNREACHABLE.format(', '.join(unreachable)))

    if not stale:
        xbmcgui.Dialog().ok(APP_NAME, DIALOG_CLEANUP_NOTHING)
        return

    stale_folders = sorted({folder for folder, _ in stale})
    preview = '\n'.join(os.path.basename(folder) for folder in stale_folders[:10])
    if len(stale_folders) > 10:
        preview += '\n...'
    if not xbmcgui.Dialog().yesno(APP_NAME, DIALOG_CLEANUP_CONFIRM.format(len(stale), len(stale_folders), preview)):
        return

    for folder, filename in stale:
        log('Cleanup: removing {}'.format(join_path(folder, filename)))
        _remove_stale_strm(folder, filename)

    removed_folders = sum(1 for folder in stale_folders if _remove_folder_if_orphaned(folder))

    xbmcgui.Dialog().ok(APP_NAME, DIALOG_CLEANUP_DONE.format(len(stale), removed_folders))
    xbmc.executebuiltin('CleanLibrary(video)')
