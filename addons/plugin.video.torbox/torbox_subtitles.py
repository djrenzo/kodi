import os

import xbmc
import xbmcgui

from torbox_common import APP_NAME, VIDEO_EXTS, extract_episode_info, load_overrides, log, save_overrides
from torbox_library import get_library_folder_for
from torbox_srt import ADJUSTMENT_KEYS, apply_adjustments
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


def _ask_srt_adjustments(dialog, dest_path):
    """Ask for an FPS conversion and a time shift, apply them to the downloaded file and
    return what was applied ({} if nothing), so it can be stored with the subtitle."""
    adjust = {}
    if dialog.yesno(APP_NAME, 'Do you want to change the subtitle FPS?'):
        old_fps = dialog.input('Enter old FPS:', defaultt='23.976')
        if old_fps:
            new_fps = dialog.input('Enter new FPS:', defaultt='25')
            if new_fps:
                try:
                    old_value, new_value = float(old_fps), float(new_fps)
                    if old_value > 0 and new_value > 0 and old_value != new_value:
                        adjust['fps_from'], adjust['fps_to'] = old_value, new_value
                except ValueError as exc:
                    log('Invalid FPS: {}'.format(exc))

    if dialog.yesno(APP_NAME, 'Do you want to shift the subtitle time?'):
        direction = dialog.yesno(APP_NAME, 'Delay subtitles? (No = advance earlier)')
        offset_str = dialog.input('Enter offset in milliseconds:', defaultt='0', type=xbmcgui.INPUT_NUMERIC)
        if offset_str:
            try:
                offset_ms = int(offset_str)
            except ValueError:
                offset_ms = 0
            if offset_ms:
                adjust['shift_ms'] = offset_ms if direction else -offset_ms

    try:
        apply_adjustments(dest_path, adjust)
    except Exception as exc:
        log('Error adjusting subtitle {}: {}'.format(dest_path, exc), xbmc.LOGWARNING)
        return {}
    return adjust


def _remember_subtitle(folder_name, metadata, adjust):
    """Store the subtitle that is now in the library in the folder's overrides 'subs'.
    An entry with the same URL is replaced, so its adjustments always describe the file
    on disk, and it moves to the end: for the same file the export uses the last entry,
    i.e. the subtitle picked most recently."""
    overrides = load_overrides()  # reload: don't overwrite edits saved since add_subtitles started
    override = overrides.get(folder_name, {})
    subs = override.get('subs', [])
    previous = next((saved for saved in subs if saved.get('url') == metadata['url']), {})
    entry = {key: value for key, value in dict(previous, **metadata).items() if key not in ADJUSTMENT_KEYS}
    entry.update(adjust)
    override['subs'] = [saved for saved in subs if saved.get('url') != metadata['url']] + [entry]
    overrides[folder_name] = override
    save_overrides(overrides)


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
            chosen = existing_subs[idx]
            if not fetcher.download_url(chosen['url'], dest_path):
                dialog.ok(APP_NAME, DIALOG_SUBS_DOWNLOAD_FAILED)
                return
            _notify_saved(dialog, dest_path, target_filename)
            # A fresh download: the adjustments asked now replace the stored ones.
            adjust = _ask_srt_adjustments(dialog, dest_path)
            _remember_subtitle(folder_name, {'url': chosen['url'], 'fileName': chosen.get('fileName') or target_filename},
                               adjust)
            return
        # Cancel/back on existing subtitles: fall through and fetch new subtitles to override.

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

    _remember_subtitle(folder_name, {
        'url': fetcher.get_subtitle_url(sub_id),
        'fileName': target_filename,
        'language': chosen.get('language', language_code),
        'hi': chosen.get('isHearingImpaired', False),
    }, {})
    _notify_saved(dialog, dest_path, target_filename)


def search_subs_imdb_id(imdb_id, subtitle_lang):
    imdb_id = (str(imdb_id) or '').strip()
    if not imdb_id:
        return []

    fetcher = OpenSubtitlesFetcher()
    return fetcher.fetch_subtitles_urls(imdb_id, language=subtitle_lang)
