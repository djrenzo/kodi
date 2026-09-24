import os
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl, unquote, urlparse

import xbmc
import xbmcgui
import xbmcvfs

from torbox_common import (
    ADDON,
    ADDON_ID,
    APP_NAME,
    SKIP_EXTS,
    VIDEO_EXTS,
    build_url,
    clean_show_name,
    extract_episode_info,
    get_account,
    get_accounts,
    load_overrides,
    log,
)
from torbox_text import (
    DIALOG_CLEANUP_CONFIRM,
    DIALOG_CLEANUP_DONE,
    DIALOG_CLEANUP_NOTHING,
    DIALOG_CLEANUP_UNREACHABLE,
    DIALOG_LIBRARY_EXPORT_DONE,
    DIALOG_LIBRARY_PATH_NOT_CONFIGURED,
    DIALOG_LIBRARY_SOURCE_ADDED,
    NOTIFY_ACCOUNT_NOT_FOUND,
    NOTIFY_NO_ACCOUNTS,
    PROGRESS_CLEANUP_ACCOUNT,
    PROGRESS_CLEANUP_LIBRARY,
    PROGRESS_CLEANUP_TITLE,
)
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

    overrides = load_overrides()
    override = overrides.get(folder_name, {})
    media_type = override.get('type', 'tvshow')

    if override:
        clean_title = override.get('title', folder_name)
        year = override.get('year')
    else:
        clean_title, year = clean_show_name(folder_name)

    if media_type == 'movie' and year:
        sub_folder = '{} ({})'.format(clean_title, year)
    else:
        sub_folder = clean_title

    media_root = get_media_library_root(library_root, media_type)
    return os.path.join(media_root, sub_folder)


def resolve_media_info(raw_name, overrides):
    """Return title/year/ids/type for a WebDAV folder, preferring its manual override."""
    override = overrides.get(raw_name, {})

    if override:
        clean_title = override.get('title', raw_name)
        year = override.get('year')
    else:
        clean_title, year = clean_show_name(raw_name)

    return {
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


def episode_basename(title, season, episode_no):
    return '{}.S{:02d}E{:02d}'.format(title, season, episode_no)


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
        folder_name = movie_folder_name(clean_title, year)
        movie_folder = join_path(movies_root, folder_name)

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
        return 1

    show_folder = join_path(tvshows_root, clean_title)
    if not xbmcvfs.exists(show_folder):
        xbmcvfs.mkdirs(show_folder)

    write_tvshow_nfo(show_folder, clean_title, tvdb_id, tmdb_id, imdb_id)

    created = 0
    for episode in walk_webdav(account, normalized_path):
        season, episode_no = extract_episode_info(episode['name'])
        if season is None:
            continue

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

    return created


def export_library(account_index):
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

    root_xml = propfind(account['url'] + '/', account['username'], account['password'], depth=1)
    if root_xml is None:
        return

    root_items = parse_propfind(root_xml, account['url'], '/')
    created = 0

    for root_item in root_items:
        if not root_item.get('is_collection'):
            continue

        raw_name = root_item.get('name')
        if not raw_name:
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

    created = _export_collection(
        account,
        account_index,
        folder_name,
        remote_path,
        load_overrides(),
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
