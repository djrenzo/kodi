import os
import xml.etree.ElementTree as ET
from urllib.parse import unquote

import xbmc
import xbmcgui
import xbmcvfs

from torbox_common import (
    ADDON,
    APP_NAME,
    VIDEO_EXTS,
    build_url,
    clean_show_name,
    extract_episode_info,
    get_account,
    load_overrides,
    log,
)
from torbox_text import (
    DIALOG_LIBRARY_EXPORT_DONE,
    DIALOG_LIBRARY_PATH_NOT_CONFIGURED,
    DIALOG_LIBRARY_SOURCE_ADDED,
    NOTIFY_ACCOUNT_NOT_FOUND,
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


def write_text_file(path, content):
    folder = os.path.dirname(path)
    if not xbmcvfs.exists(folder):
        xbmcvfs.mkdirs(folder)

    with xbmcvfs.File(path, 'w') as fh:
        fh.write(content)


def write_tvshow_nfo(show_folder, title, tvdb_id=None, tmdb_id=None):
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
    xml.append('</tvshow>')

    write_text_file(os.path.join(show_folder, 'tvshow.nfo'), '\n'.join(xml))


def write_movie_nfo(movie_folder, title, year=None, tmdb_id=None):
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
    xml.append('</movie>')

    write_text_file(os.path.join(movie_folder, 'movie.nfo'), '\n'.join(xml))


def get_media_library_root(library_root, media_type):
    if media_type == 'movie':
        return os.path.join(library_root, 'movies')
    return os.path.join(library_root, 'tvshows')


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


def _export_collection(account, account_index, raw_name, child_path, overrides, movies_root, tvshows_root):
    override = overrides.get(raw_name, {})
    media_type = override.get('type', 'tvshow')

    if override:
        clean_title = override.get('title', raw_name)
        year = override.get('year')
        tvdb_id = override.get('tvdb_id')
        tmdb_id = override.get('tmdb_id')
    else:
        clean_title, year = clean_show_name(raw_name)
        tvdb_id = None
        tmdb_id = None

    normalized_path = unquote(child_path or '')
    if not normalized_path:
        return 0

    if not normalized_path.endswith('/'):
        normalized_path += '/'

    if media_type == 'movie':
        folder_name = '{} ({})'.format(clean_title, year) if year else clean_title
        movie_folder = os.path.join(movies_root, folder_name)

        if not xbmcvfs.exists(movie_folder):
            xbmcvfs.mkdirs(movie_folder)

        write_movie_nfo(movie_folder, clean_title, year, tmdb_id)
        video_item = find_main_video(account, normalized_path)

        if video_item is None:
            log('No video found for movie: {}'.format(raw_name), xbmc.LOGWARNING)
            return 0

        strm_name = '{}.strm'.format(folder_name)
        strm_path = os.path.join(movie_folder, strm_name)
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

    show_folder = os.path.join(tvshows_root, clean_title)
    if not xbmcvfs.exists(show_folder):
        xbmcvfs.mkdirs(show_folder)

    write_tvshow_nfo(show_folder, clean_title, tvdb_id, tmdb_id)

    created = 0
    for episode in walk_webdav(account, normalized_path):
        season, episode_no = extract_episode_info(episode['name'])
        if season is None:
            continue

        strm_name = '{}.S{:02d}E{:02d}.strm'.format(clean_title, season, episode_no)
        strm_path = os.path.join(show_folder, strm_name)
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
