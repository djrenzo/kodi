import os

import xbmc
import xbmcgui

from torbox_common import APP_NAME, VIDEO_EXTS, extract_episode_info, load_overrides, log, save_overrides
from torbox_library import get_library_folder_for
from torbox_srt import convert_srt_fps, shift_srt_time
from torbox_wyzie import OpenSubtitlesFetcher, WyzieFetcher
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


def _apply_srt_adjustments(dialog, dest_path):
    if dialog.yesno(APP_NAME, 'Do you want to change the subtitle FPS?'):
        old_fps = dialog.input('Enter old FPS:', defaultt='23.976')
        if old_fps:
            new_fps = dialog.input('Enter new FPS:', defaultt='25')
            if new_fps:
                try:
                    convert_srt_fps(dest_path, dest_path, old_fps=float(old_fps), new_fps=float(new_fps))
                except (ValueError, Exception) as exc:
                    log('Error converting FPS: {}'.format(exc))

    if dialog.yesno(APP_NAME, 'Do you want to shift the subtitle time?'):
        direction = dialog.yesno(APP_NAME, 'Delay subtitles? (No = advance earlier)')
        offset_str = dialog.input('Enter offset in milliseconds:', defaultt='0', type=xbmcgui.INPUT_NUMERIC)
        if offset_str:
            offset_ms = int(offset_str)
            if not direction:
                offset_ms = -offset_ms
            try:
                shift_srt_time(dest_path, dest_path, offset_ms=offset_ms)
            except (ValueError, Exception) as exc:
                log('Error shifting subtitle time: {}'.format(exc))


def _notify_saved(dialog, dest_path, target_filename):
    dialog.notification(APP_NAME, NOTIFY_SUBTITLE_SAVED.format(target_filename), xbmcgui.NOTIFICATION_INFO, 3000)
    log('Subtitle saved to {} and recorded in overrides'.format(dest_path))


def add_subtitles(folder_name, account_index):
    del account_index

    fetcher = WyzieFetcher()
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
    dest_path = os.path.join(library_folder, target_filename)

    existing_subs = [
        s for s in subs
        if s.get('language', 'en') == language_code
        and s.get('fileName', '').startswith(target_basename)
    ]
    if existing_subs:
        def existing_label(result):
            hi = ' [HI]' if result.get('hi') else ''
            lang = ' ({})'.format(result['language']) if result.get('language') else ''
            return '{}{}{}'.format(result.get('fileName'), hi, lang)

        idx = dialog.select(DIALOG_SUBS_EXISTING, [existing_label(s) for s in existing_subs])
        if idx >= 0:
            subtitle_url = existing_subs[idx]['url']
            if not fetcher.download(subtitle_url, dest_path):
                dialog.ok(APP_NAME, DIALOG_SUBS_DOWNLOAD_FAILED)
                return
            _notify_saved(dialog, dest_path, target_filename)
            _apply_srt_adjustments(dialog, dest_path)
        return

    if not tmdb_id:
        dialog.ok(DIALOG_SUBS_ADD_TITLE.format(APP_NAME), DIALOG_SUBS_NEED_TMDB)
        return

    season, episode = (extract_episode_info(target_basename) if media_type == 'tvshow' else (None, None))

    dialog.notification(APP_NAME, NOTIFY_SEARCHING_SUBS, xbmcgui.NOTIFICATION_INFO, 2000)
    results = fetcher.fetch_subtitles(tmdb_id, language=language_code, season=season, episode=episode)
    if not results and media_type == 'tvshow' and season is not None and episode is not None:
        # Fallback: provider may lack episode-indexed results.
        results = fetcher.fetch_subtitles(tmdb_id, language=language_code)

    if not results:
        dialog.ok(APP_NAME, DIALOG_SUBS_NOT_FOUND.format(tmdb_id))
        return

    def result_label(result):
        hi = ' [HI]' if result.get('isHearingImpaired') else ''
        origin = ' ({})'.format(result['origin']) if result.get('origin') else ''
        downloads = '  v{:,}'.format(result['downloadCount']) if result.get('downloadCount') else ''
        return '{}{}{}{}'.format(result.get('fileName', result['id']), hi, origin, downloads)

    idx = dialog.select(DIALOG_SUBS_PICK, [result_label(r) for r in results])
    if idx < 0:
        return

    chosen = results[idx]
    sub_id = chosen.get('id')
    if not fetcher.download(sub_id, dest_path):
        dialog.ok(APP_NAME, DIALOG_SUBS_DOWNLOAD_FAILED)
        return

    subtitle_url = fetcher.get_subtitle_url(sub_id)
    if not any(saved.get('url') == subtitle_url for saved in subs):
        metadata = {
            'url': subtitle_url,
            'fileName': target_filename,
            'language': chosen.get('language', language_code),
            'hi': chosen.get('isHearingImpaired', False),
        }
        subs.append(metadata)
        fetcher.save(dest_path, metadata)

    override['subs'] = subs
    overrides[folder_name] = override
    save_overrides(overrides)
    _notify_saved(dialog, dest_path, target_filename)


def search_subs_imdb_id(imdb_id, subtitle_lang):
    imdb_id = (imdb_id or '').strip()
    if not imdb_id:
        return []

    fetcher = OpenSubtitlesFetcher()
    return fetcher.fetch_subtitles_urls(imdb_id, language=subtitle_lang)
