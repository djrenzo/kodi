import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmc
import xbmcgui
import xbmcvfs

from torbox_common import APP_NAME, VIDEO_EXTS, extract_episode_info, load_overrides, log, save_overrides
from torbox_library import get_library_folder_for
from torbox_text import (
    DIALOG_LIBRARY_SUBS_EXPORT_FIRST,
    DIALOG_SUBS_ADD_TITLE,
    DIALOG_SUBS_BAD_RESULT,
    DIALOG_SUBS_DOWNLOAD_FAILED,
    DIALOG_SUBS_EXISTING,
    DIALOG_SUBS_LANG_EN,
    DIALOG_SUBS_LANG_ES,
    DIALOG_SUBS_LANG_SP,
    DIALOG_SUBS_LANGUAGE,
    DIALOG_SUBS_NEED_TMDB,
    DIALOG_SUBS_NO_VIDEO_FILES,
    DIALOG_SUBS_NOT_FOUND,
    DIALOG_SUBS_PICK,
    DIALOG_SUBS_PICK_VIDEO,
    NOTIFY_SEARCHING_SUBS,
    NOTIFY_SUBTITLE_SAVED,
)

WYZIE_API = 'https://sub.wyzie.io/search'
WYZIE_KEY = 'wyzie-gvo9qomam6re1xxww2krz89m7f0ww4ax'
WYZIE_LIMIT = 10
SUBTITLE_EXTS = ('.srt', '.ass', '.ssa', '.sub', '.vtt')
SRT_LANG_CODES = {"en": "en",
                  "es": "es",
                  "sp": "es"}


def _pick_video_basename(dialog, library_folder):
    video_exts = set(VIDEO_EXTS)
    video_exts.add('.strm')

    candidates = []
    try:
        for filename in sorted(os.listdir(library_folder), key=lambda value: value.lower()):
            root, ext = os.path.splitext(filename)
            if ext.lower() in video_exts and root:
                candidates.append(filename)
    except Exception as exc:
        log('pick_video_basename error: {}'.format(exc), xbmc.LOGWARNING)
        return None

    if not candidates:
        return None

    if len(candidates) == 1:
        return os.path.splitext(candidates[0])[0]

    choice = dialog.select(DIALOG_SUBS_PICK_VIDEO, candidates)
    if choice < 0:
        return ''
    return os.path.splitext(candidates[choice])[0]


def fetch_subtitles(tmdb_id, language='en', season=None, episode=None):
    params_data = {'id': tmdb_id, 'format': 'srt', 'language': language, 'key': WYZIE_KEY}
    if season is not None:
        params_data['season'] = int(season)
    if episode is not None:
        params_data['episode'] = int(episode)

    params = urlencode(params_data)
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
    video_basename = os.path.splitext(os.path.basename(strm_path))[0]
    found = []

    try:
        for filename in os.listdir(folder):
            root, ext = os.path.splitext(filename)
            if root.startswith(video_basename) and ext.lower() in SUBTITLE_EXTS:
                found.append(os.path.join(folder, filename))
    except Exception as exc:
        log('find_local_subtitles error: {}'.format(exc), xbmc.LOGWARNING)

    return sorted(found, key=lambda value: value.lower())


def add_subtitles(folder_name, account_index):
    del account_index

    overrides = load_overrides()
    override = overrides.get(folder_name, {})
    tmdb_id = override.get('tmdb_id', '').strip()
    media_type = override.get('type', 'tvshow')
    subs = override.get('subs', [])

    dialog = xbmcgui.Dialog()
    library_folder = get_library_folder_for(folder_name)
    if not library_folder:
        dialog.ok(APP_NAME, DIALOG_LIBRARY_SUBS_EXPORT_FIRST)
        return

    target_basename = _pick_video_basename(dialog, library_folder)
    if target_basename == '':
        return
    if target_basename is None:
        dialog.ok(APP_NAME, DIALOG_SUBS_NO_VIDEO_FILES)
        return

    language_options = [DIALOG_SUBS_LANG_EN, DIALOG_SUBS_LANG_ES, DIALOG_SUBS_LANG_SP]
    language_codes = ['en', 'es', 'sp']
    lang_idx = dialog.select(DIALOG_SUBS_LANGUAGE, language_options)
    if lang_idx < 0:
        return
    language_code = language_codes[lang_idx]

    target_filename = '{}.{}.srt'.format(target_basename, SRT_LANG_CODES[language_code])

    def existing_label(result):
        hearing_impaired = ' [HI]' if result.get('hi') else ''
        language = ' ({})'.format(result['language']) if result.get('language') else ''
        return '{}{}{}'.format(result.get('fileName'), hearing_impaired, language)

    existing_subs = [result for result in subs if result.get('language', 'en') == language_code and result.get('fileName', '').startswith(target_basename)]
    if existing_subs:
        idx = dialog.select(DIALOG_SUBS_EXISTING, [existing_label(result) for result in existing_subs])
        if idx >= 0:
            chosen = existing_subs[idx]
            subtitle_url = chosen['url']

            dest_path = os.path.join(library_folder, target_filename)
            if not download_subtitle(subtitle_url, dest_path):
                dialog.ok(APP_NAME, DIALOG_SUBS_DOWNLOAD_FAILED)
                return

            dialog.notification(APP_NAME, NOTIFY_SUBTITLE_SAVED.format(target_filename), xbmcgui.NOTIFICATION_INFO, 3000)
            log('Subtitle saved to {} and recorded in overrides'.format(dest_path))
            return

    if not tmdb_id:
        dialog.ok(
            DIALOG_SUBS_ADD_TITLE.format(APP_NAME),
            DIALOG_SUBS_NEED_TMDB,
        )
        return

    season = None
    episode = None
    if media_type == 'tvshow':
        season, episode = extract_episode_info(target_basename)

    dialog.notification(APP_NAME, NOTIFY_SEARCHING_SUBS, xbmcgui.NOTIFICATION_INFO, 2000)
    results = fetch_subtitles(tmdb_id, language=language_code, season=season, episode=episode)
    if not results and media_type == 'tvshow' and season is not None and episode is not None:
        # Fallback for cases where provider has no episode-indexed result for the title.
        results = fetch_subtitles(tmdb_id, language=language_code)

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

    dest_path = os.path.join(library_folder, target_filename)
    if not download_subtitle(subtitle_url, dest_path):
        dialog.ok(APP_NAME, DIALOG_SUBS_DOWNLOAD_FAILED)
        return

    subs = override.get('subs', [])
    if not any(saved.get('url') == subtitle_url for saved in subs):
        subs.append(
            {
                'url': subtitle_url,
                'fileName': target_filename,
                'language': chosen.get('language', language_code),
                'hi': chosen.get('isHearingImpaired', False),
            }
        )

    override['subs'] = subs
    overrides[folder_name] = override
    save_overrides(overrides)

    dialog.notification(APP_NAME, NOTIFY_SUBTITLE_SAVED.format(target_filename), xbmcgui.NOTIFICATION_INFO, 3000)
    log('Subtitle saved to {} and recorded in overrides'.format(dest_path))


def search_subs_imdb_id(imdb_id, subtitle_lang):
    imdb_id = (imdb_id or '').strip()
    if not imdb_id:
        return []

    url_stream = (
        'https://opensubtitles-v3.strem.io/subtitles/movie/{}/filename=t.json'
    ).format(imdb_id)

    try:
        request = Request(url_stream, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request, timeout=15) as response:
            raw_stream = response.read().decode('utf-8')
    except (HTTPError, URLError) as exc:
        log('search: failed to fetch {}: {}'.format(url_stream, exc), xbmc.LOGWARNING)
        return []

    try:
        data = json.loads(raw_stream).get('subtitles', [])
        # Filter subtitles by the specified language
        return [sub.get('url') for sub in data if sub.get('lang') == subtitle_lang]
    except ValueError as exc:
        log('search: invalid JSON from {}: {}'.format(url_stream, exc), xbmc.LOGWARNING)
        return []
