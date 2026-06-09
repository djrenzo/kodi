import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmc
import xbmcgui
import xbmcvfs

from torbox_common import APP_NAME, load_overrides, log, save_overrides
from torbox_library import get_library_folder_for
from torbox_text import (
    DIALOG_LIBRARY_SUBS_EXPORT_FIRST,
    DIALOG_SUBS_ADD_TITLE,
    DIALOG_SUBS_BAD_RESULT,
    DIALOG_SUBS_DOWNLOAD_FAILED,
    DIALOG_SUBS_EXISTING,
    DIALOG_SUBS_NEED_TMDB,
    DIALOG_SUBS_NOT_FOUND,
    DIALOG_SUBS_PICK,
    NOTIFY_SEARCHING_SUBS,
    NOTIFY_SUBTITLE_SAVED,
)

WYZIE_API = 'https://sub.wyzie.io/search'
WYZIE_KEY = 'wyzie-gvo9qomam6re1xxww2krz89m7f0ww4ax'
WYZIE_LIMIT = 10


def fetch_subtitles(tmdb_id, language='en'):
    params = urlencode({'id': tmdb_id, 'format': 'srt', 'language': language, 'key': WYZIE_KEY})
    url = '{}?{}'.format(WYZIE_API, params)
    log('Wyzie query: {}'.format(url))

    try:
        req = Request(url, headers={'User-Agent': 'Kodi/TorBox-Plugin'})
        response = urlopen(req, timeout=15)
        data = json.loads(response.read().decode('utf-8'))
        return data[:WYZIE_LIMIT] if isinstance(data, list) else []
    except Exception as exc:
        log('fetch_subtitles error: {}'.format(exc), xbmc.LOGWARNING)
        return []


def download_subtitle(sub_url, dest_path):
    log('Downloading subtitle: {}'.format(sub_url))

    try:
        req = Request(sub_url, headers={'User-Agent': 'Kodi/TorBox-Plugin'})
        response = urlopen(req, timeout=30)
        data = response.read()

        folder = os.path.dirname(dest_path)
        if not xbmcvfs.exists(folder):
            xbmcvfs.mkdirs(folder)

        with xbmcvfs.File(dest_path, 'w') as fh:
            fh.write(data.decode('utf-8', errors='replace'))
        return True
    except Exception as exc:
        log('download_subtitle error: {}'.format(exc), xbmc.LOGWARNING)
        return False


def find_local_subtitles(strm_path):
    if not strm_path:
        return []

    folder = os.path.dirname(strm_path)
    sub_exts = ('.srt', '.ass', '.ssa', '.sub', '.vtt')
    found = []

    try:
        for filename in os.listdir(folder):
            if os.path.splitext(filename)[1].lower() in sub_exts:
                found.append(os.path.join(folder, filename))
    except Exception as exc:
        log('find_local_subtitles error: {}'.format(exc), xbmc.LOGWARNING)

    return found


def add_subtitles(folder_name, account_index):
    del account_index

    overrides = load_overrides()
    override = overrides.get(folder_name, {})
    tmdb_id = override.get('tmdb_id', '').strip()
    subs = override.get('subs', [])

    dialog = xbmcgui.Dialog()

    def existing_label(result):
        hearing_impaired = ' [HI]' if result.get('hi') else ''
        language = ' ({})'.format(result['language']) if result.get('language') else ''
        return '{}{}{}'.format(result.get('fileName'), hearing_impaired, language)

    if subs:
        idx = dialog.select(DIALOG_SUBS_EXISTING, [existing_label(result) for result in subs])
        if idx >= 0:
            chosen = subs[idx]
            subtitle_url = chosen['url']
            filename = chosen.get('fileName')

            library_folder = get_library_folder_for(folder_name)
            if not library_folder:
                dialog.ok(APP_NAME, DIALOG_LIBRARY_SUBS_EXPORT_FIRST)
                return

            dest_path = os.path.join(library_folder, filename)
            if not download_subtitle(subtitle_url, dest_path):
                dialog.ok(APP_NAME, DIALOG_SUBS_DOWNLOAD_FAILED)
                return

            dialog.notification(APP_NAME, NOTIFY_SUBTITLE_SAVED.format(filename), xbmcgui.NOTIFICATION_INFO, 3000)
            log('Subtitle saved to {} and recorded in overrides'.format(dest_path))
            return

    if not tmdb_id:
        dialog.ok(
            DIALOG_SUBS_ADD_TITLE.format(APP_NAME),
            DIALOG_SUBS_NEED_TMDB,
        )
        return

    dialog.notification(APP_NAME, NOTIFY_SEARCHING_SUBS, xbmcgui.NOTIFICATION_INFO, 2000)
    results = fetch_subtitles(tmdb_id)

    if not results:
        dialog.ok(APP_NAME, DIALOG_SUBS_NOT_FOUND.format(tmdb_id))
        return

    def result_label(result):
        hearing_impaired = ' [HI]' if result.get('isHearingImpaired') else ''
        origin = ' ({})'.format(result['origin']) if result.get('origin') else ''
        downloads = '  v{:,}'.format(result['downloadCount']) if result.get('downloadCount') else ''
        return '{}{}{}{}'.format(result.get('fileName', result['id']), hearing_impaired, origin, downloads)

    idx = dialog.select(DIALOG_SUBS_PICK, [result_label(result) for result in results])
    if idx < 0:
        return

    chosen = results[idx]
    subtitle_url = chosen.get('url')
    if not subtitle_url:
        dialog.ok(APP_NAME, DIALOG_SUBS_BAD_RESULT)
        return

    language_code = 'en'
    file_name = chosen.get('fileName') or ''
    filename_root = file_name.split('.')[0] if file_name else chosen.get('id', 'subtitle')
    filename = '{}.{}.srt'.format(filename_root, language_code)

    library_folder = get_library_folder_for(folder_name)
    if not library_folder:
        dialog.ok(APP_NAME, DIALOG_LIBRARY_SUBS_EXPORT_FIRST)
        return

    dest_path = os.path.join(library_folder, filename)
    if not download_subtitle(subtitle_url, dest_path):
        dialog.ok(APP_NAME, DIALOG_SUBS_DOWNLOAD_FAILED)
        return

    subs = override.get('subs', [])
    if not any(saved.get('url') == subtitle_url for saved in subs):
        subs.append(
            {
                'url': subtitle_url,
                'fileName': filename,
                'language': chosen.get('language', 'en'),
                'hi': chosen.get('isHearingImpaired', False),
            }
        )

    override['subs'] = subs
    overrides[folder_name] = override
    save_overrides(overrides)

    dialog.notification(APP_NAME, NOTIFY_SUBTITLE_SAVED.format(filename), xbmcgui.NOTIFICATION_INFO, 3000)
    log('Subtitle saved to {} and recorded in overrides'.format(dest_path))
