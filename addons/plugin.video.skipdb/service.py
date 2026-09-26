# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 TheIntroDB (original plugin.video.tidb)
#
# kodi service entry: poll playback, query skipdb, show skip ui or auto-seek
import xbmc
import xbmcaddon
import xbmcgui
from typing import List, Dict, Optional, Any, Tuple

from player import SkipDBPlayer
import skipper
import overlay as overlay_mod
import submit_overlay
import skipdb

ADDON = xbmcaddon.Addon()
_ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')

# String IDs for localization
STR_SKIP_INTRO = 32001
STR_SKIP_RECAP = 32003
STR_SKIP_CREDITS = 32004
STR_SKIP_PREVIEW = 32005
STR_MARK_START = 32020
STR_MARK_END = 32021
STR_SUBMIT_SUCCESS = 32022
STR_SUBMIT_FAILED = 32023
STR_PICK_SEGMENT_TYPE = 32046
STR_SEGMENT_LABELS = {
    'intro': 32047,
    'recap': 32048,
    'credits': 32049,
    'preview': 32050,
}
STR_ALREADY_IN_SKIPDB = 32051

SEGMENT_TYPES = ('intro', 'recap', 'credits', 'preview')

# end-of-stream tolerance: an outro/preview ending this close to the end is treated as "runs to the end"
END_OF_MEDIA_TOLERANCE_SECS = 10.0


class SkipDBMonitor(xbmc.Monitor):
    pass


def _debug_osd(message: str) -> None:
    # optional toast spam for debugging
    if ADDON.getSetting('debug_osd') == 'true':
        xbmc.executebuiltin('Notification(SkipDB, {}, 1500)'.format(message))


def _fresh_bool(key: str) -> bool:
    # read setting again from disk so gui changes apply without restart
    try:
        return xbmcaddon.Addon(_ADDON_ID).getSetting(key) == 'true'
    except Exception:
        return ADDON.getSetting(key) == 'true'


def _debug_logging() -> bool:
    return ADDON.getSetting('debug_logging') == 'true'


def _run_api_key_test() -> None:
    """Validate the configured API key and present the result."""
    xbmc.log('[SkipDB] Running API key test from settings', xbmc.LOGINFO)
    success, msg = skipdb.test_api_key()
    xbmc.log('[SkipDB] API key test result: {}'.format(msg), xbmc.LOGINFO)
    xbmcgui.Dialog().ok('SkipDB API', msg)


def _run_get_anonymous_key() -> None:
    """Create an anonymous SkipDB API key and store it in the settings."""
    xbmc.log('[SkipDB] Requesting anonymous API key from settings', xbmc.LOGINFO)
    dialog = xbmcgui.Dialog()
    try:
        current = (xbmcaddon.Addon(_ADDON_ID).getSetting('skipdb_api_key') or '').strip()
    except Exception:
        current = ''
    if current and not dialog.yesno(
            'SkipDB API',
            'An API key is already configured. Replace it with a new anonymous key?'):
        return

    key, msg = skipdb.create_anonymous_key()
    if not key:
        xbmc.log('[SkipDB] Anonymous key request failed: {}'.format(msg), xbmc.LOGWARNING)
        dialog.ok('SkipDB API', msg)
        return

    xbmcaddon.Addon(_ADDON_ID).setSetting('skipdb_api_key', key)
    xbmc.log('[SkipDB] Anonymous API key stored (prefix {})'.format(key[:14]), xbmc.LOGINFO)
    dialog.ok(
        'SkipDB API',
        'Anonymous API key saved to the addon settings:[CR][B]{}[/B][CR][CR]'
        'There is no account to recover it from, so keep a copy.'.format(key),
    )


# ── Playback session state ────────────────────────────────────────────────

class PlaybackSession:
    """Holds all mutable state for one file's playback."""
    current_file: Optional[str]
    media_ids: Optional[Dict[str, Any]]
    all_segments: Optional[Dict[str, Any]]
    processed_segments: Dict[str, Dict[str, Any]]
    next_episode_info: Optional[Dict[str, Any]]
    next_episode_checked: bool
    submit_start_sec: Optional[float]
    submit_prompted_this_pause: bool
    submitted_types: set
    last_seen_pause_count: int

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.current_file = None
        self.media_ids = None
        self.all_segments = None
        self.processed_segments = {}
        self.next_episode_info = None
        self.next_episode_checked = False
        # Submission state
        self.submit_start_sec = None
        self.submit_prompted_this_pause = False
        self.submitted_types = set()
        self.last_seen_pause_count = 0


# ── Segment collection ────────────────────────────────────────────────────

def _collect_enabled_segments(all_segments: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Gather all enabled segments from the API response, sorted chronologically."""
    result = []
    for segment_type in SEGMENT_TYPES:
        if not _fresh_bool('enable_{}'.format(segment_type)):
            continue
        segments = all_segments.get(segment_type, [])
        for idx, seg in enumerate(segments):
            entry = seg.copy()
            entry['type'] = segment_type
            entry['index'] = idx
            result.append(entry)

    result.sort(key=lambda x: x['start'] if x['start'] is not None else 0)
    return result


# ── Skip / next-episode handling ──────────────────────────────────────────

def _resolve_segment_bounds(segment: Dict[str, Any], player: SkipDBPlayer) -> Optional[Tuple[float, float, bool]]:
    """Normalise start/end; returns (start, end, is_next_episode_candidate) or None."""
    api_start = segment['start']
    api_end = segment['end']

    if api_start is None and api_end is None:
        return None

    if api_start is None:
        api_start = 0

    try:
        total_time = player.getTotalTime()
    except Exception:
        total_time = 0

    # SkipDB outros default to the stream duration, so "runs to the end" usually arrives as a
    # real end_ms at (or within a few seconds of) the total time rather than null.
    runs_to_end = api_end is None or (total_time > 0 and api_end >= total_time - END_OF_MEDIA_TOLERANCE_SECS)
    is_next_ep = segment['type'] in ('credits', 'preview') and runs_to_end

    if api_end is None:
        if total_time <= 0:
            return None
        api_end = total_time - 10

    return api_start, api_end, is_next_ep


def _show_skip_overlay(player: SkipDBPlayer, monitor: xbmc.Monitor, api_end: float, segment_type: str, segment_idx: int) -> Optional[bool]:
    """Show the standard skip pill and return whether it was pressed."""
    if monitor.abortRequested():
        return None  # signal to break the outer loop
    return overlay_mod.show_skip_overlay(
        intro_end=api_end,
        player=player,
        monitor=monitor,
        segment_type=segment_type,
        segment_index=segment_idx,
    )


def _handle_segment(segment: Dict[str, Any], segment_idx: int, player: SkipDBPlayer, monitor: xbmc.Monitor, session: PlaybackSession, filename: str) -> Optional[str]:
    """Process a single segment: auto-skip, next-episode, or show skip button.

    Returns 'break' if the service loop should exit, else None.
    """
    bounds = _resolve_segment_bounds(segment, player)
    if bounds is None:
        return None
    api_start, api_end, is_next_ep = bounds

    segment_type = segment['type']
    segment_key = '{}_{}'.format(segment_type, segment_idx)

    if _debug_logging():
        xbmc.log('[SkipDB] Processing {} segment {}: start={}, end={}'.format(
            segment_type, segment_idx, api_start, api_end), xbmc.LOGINFO)

    current_time = player.getTime() if player.isPlaying() else 0

    if not _should_show_segment_button(session.processed_segments, segment_key,
                                       current_time, api_start, api_end):
        return None

    if not player.isPlaying():
        return None

    # Resolve display name
    segment_names = {
        'intro': ADDON.getLocalizedString(STR_SKIP_INTRO),
        'recap': ADDON.getLocalizedString(STR_SKIP_RECAP),
        'credits': ADDON.getLocalizedString(STR_SKIP_CREDITS),
        'preview': ADDON.getLocalizedString(STR_SKIP_PREVIEW),
    }
    segment_name = segment_names.get(segment_type, segment_type.title())
    overlay_type = segment_type

    # out-of-range = SkipDB's closest data is for a noticeably different cut; offer the button, never auto-seek
    uncertain = segment.get('match') == 'out-of-range'
    if uncertain and _debug_logging():
        xbmc.log('[SkipDB] {} match is out-of-range; not auto-skipping'.format(segment_name), xbmc.LOGINFO)

    if _fresh_bool('auto_skip_{}'.format(segment_type)) and not uncertain:
        skipper.execute_skip(player, api_start, api_end, filename, segment_type)
        _debug_osd('Auto-skipped {}'.format(segment_name))
        xbmc.log('[SkipDB] Auto-skipped {} to {:.1f}s'.format(segment_name, api_end), xbmc.LOGINFO)
        return None

    # Check for next-episode promotion
    if is_next_ep:
        if not session.next_episode_checked:
            session.next_episode_info = player.get_next_episode()
            session.next_episode_checked = True
        if session.next_episode_info:
            return _handle_next_episode(
                player, monitor, session, api_end, segment_type, segment_idx)

    # Show skip button
    xbmc.log('[SkipDB] Showing skip overlay for {}'.format(segment_name), xbmc.LOGINFO)
    pressed = _show_skip_overlay(player, monitor, api_end, overlay_type, segment_idx)
    if pressed is None:
        return 'break'
    if pressed:
        xbmc.log('[SkipDB] User pressed Skip {}'.format(segment_name), xbmc.LOGINFO)
        skipper.execute_skip(player, api_start, api_end, filename, segment_type)
        _debug_osd('Skipped {} to {:.1f}s'.format(segment_name, api_end))
    else:
        xbmc.log('[SkipDB] User did NOT skip {}'.format(segment_name), xbmc.LOGINFO)
    return None


def _handle_next_episode(player: SkipDBPlayer, monitor: xbmc.Monitor, session: PlaybackSession, api_end: float, segment_type: str, segment_idx: int) -> Optional[str]:
    """Show 'Next Episode' overlay and act on the result."""
    if monitor.abortRequested():
        return 'break'

    overlay_mod.ADDON.getLocalizedString(overlay_mod.STR_NEXT_EPISODE)
    xbmc.log('[SkipDB] Showing Next Episode for end-of-media {} segment'.format(segment_type),
             xbmc.LOGINFO)

    pressed = overlay_mod.show_skip_overlay(
        intro_end=api_end,
        player=player,
        monitor=monitor,
        segment_type='next_episode',
        segment_index=segment_idx,
    )
    if pressed:
        xbmc.log('[SkipDB] User pressed Next Episode', xbmc.LOGINFO)
        was_opened = player.play_next_episode(session.next_episode_info)
        if was_opened:
            _debug_osd('Next Episode')
        else:
            xbmc.log('[SkipDB] Next episode was no longer available to open', xbmc.LOGWARNING)
    else:
        xbmc.log('[SkipDB] User did NOT press Next Episode', xbmc.LOGINFO)
    return None


# ── Pause-detection submission ────────────────────────────────────────────

def _handle_submit_tick(session: PlaybackSession, player: SkipDBPlayer, monitor: xbmc.Monitor, all_segments: Dict[str, Any], media_ids: Dict[str, Any]) -> bool:
    """Check for a pause event and run the mark-start / mark-end / submit flow.

    Mutates session in place. Returns True if the segment cache should be invalidated.
    """
    is_paused = player.is_paused
    current_pause_count = player.pause_count

    # Detect fresh pause edge via callback-driven counter
    if current_pause_count > session.last_seen_pause_count:
        session.submit_prompted_this_pause = False
        session.last_seen_pause_count = current_pause_count

    if not _should_offer_submit(session, is_paused, media_ids):
        return False

    try:
        current_time = player.getTime()
    except Exception:
        return False

    xbmc.log('[SkipDB] Submit flow active at {:.1f}s'.format(current_time), xbmc.LOGINFO)
    session.submit_prompted_this_pause = True

    if session.submit_start_sec is None:
        _mark_start(session, player, monitor, current_time)
        return False

    if current_time <= session.submit_start_sec:
        return False

    return _mark_end_and_submit(session, player, monitor, current_time, all_segments, media_ids)


def _should_offer_submit(session: PlaybackSession, is_paused: bool, media_ids: Dict[str, Any]) -> bool:
    """Guard: all preconditions for showing the submit prompt."""
    announce = is_paused and not session.submit_prompted_this_pause
    if not _fresh_bool('enable_submissions'):
        if announce:
            xbmc.log('[SkipDB] Submit blocked: enable_submissions is off', xbmc.LOGINFO)
        return False
    try:
        api_key = (xbmcaddon.Addon(_ADDON_ID).getSetting('skipdb_api_key') or '').strip()
    except Exception:
        api_key = (ADDON.getSetting('skipdb_api_key') or '').strip()
    if not api_key:
        if announce:
            xbmc.log('[SkipDB] Submit blocked: no API key configured', xbmc.LOGINFO)
        return False
    if not media_ids.get('lookup_imdb_id'):
        if announce:
            xbmc.log('[SkipDB] Submit blocked: no IMDb id for this item', xbmc.LOGINFO)
        return False
    if len(session.submitted_types) >= len(SEGMENT_TYPES):
        if announce:
            xbmc.log('[SkipDB] Submit blocked: every segment type already submitted for this file', xbmc.LOGINFO)
        return False
    if not is_paused:
        return False
    if session.submit_prompted_this_pause:
        return False
    xbmc.log('[SkipDB] Submit guards passed — showing overlay', xbmc.LOGINFO)
    return True


def _mark_start(session: PlaybackSession, player: SkipDBPlayer, monitor: xbmc.Monitor, current_time: float) -> None:
    """Phase 1: show the 'Mark Segment Start' pill."""
    label = ADDON.getLocalizedString(STR_MARK_START)
    xbmc.log('[SkipDB] Showing Mark Start at {:.1f}s'.format(current_time), xbmc.LOGINFO)

    pressed = submit_overlay.show_submit_mark_overlay(
        label_text=label, player=player, monitor=monitor)
    if pressed:
        session.submit_start_sec = current_time
        xbmc.log('[SkipDB] Marked segment start: {:.1f}s'.format(current_time), xbmc.LOGINFO)
        xbmc.executebuiltin(
            'Notification(SkipDB, Start marked at {:.0f}s — pause at end of segment, 2000)'.format(
                current_time))


def _guess_segment_type(start: float, player: SkipDBPlayer) -> str:
    """Best guess for preselecting the type dialog: early = intro, late = credits."""
    try:
        total = player.getTotalTime()
    except Exception:
        total = 0
    if total > 0 and start >= total * 0.7:
        return 'credits'
    return 'intro'


def _pick_segment_type(session: PlaybackSession, player: SkipDBPlayer, start: float, all_segments: Dict[str, Any]) -> Optional[str]:
    """Ask which kind of segment was marked. Returns the local type name or None if cancelled."""
    choices = [t for t in SEGMENT_TYPES if t not in session.submitted_types]
    labels = []
    for seg_type in choices:
        label = ADDON.getLocalizedString(STR_SEGMENT_LABELS[seg_type])
        if all_segments.get(seg_type):
            label = '{} {}'.format(label, ADDON.getLocalizedString(STR_ALREADY_IN_SKIPDB))
        labels.append(label)

    guess = _guess_segment_type(start, player)
    preselect = choices.index(guess) if guess in choices else 0
    idx = xbmcgui.Dialog().select(ADDON.getLocalizedString(STR_PICK_SEGMENT_TYPE), labels, preselect=preselect)
    if idx < 0:
        return None
    return choices[idx]


def _mark_end_and_submit(session: PlaybackSession, player: SkipDBPlayer, monitor: xbmc.Monitor, current_time: float,
                         all_segments: Dict[str, Any], media_ids: Dict[str, Any]) -> bool:
    """Phase 2: show the 'Mark Segment End' pill, pick the type, validate, confirm, and submit.

    Returns True if the segment cache should be invalidated.
    """
    label = ADDON.getLocalizedString(STR_MARK_END)
    xbmc.log('[SkipDB] Showing Mark End at {:.1f}s'.format(current_time), xbmc.LOGINFO)

    pressed = submit_overlay.show_submit_mark_overlay(
        label_text=label, player=player, monitor=monitor)
    if not pressed:
        return False

    start = session.submit_start_sec
    end = current_time
    duration = end - start
    xbmc.log('[SkipDB] Marked segment end: {:.1f}s (duration {:.1f}s)'.format(end, duration),
             xbmc.LOGINFO)

    segment_type = _pick_segment_type(session, player, start, all_segments)
    if segment_type is None:
        session.submit_start_sec = None
        xbmc.log('[SkipDB] User cancelled segment type selection', xbmc.LOGINFO)
        return False
    type_label = ADDON.getLocalizedString(STR_SEGMENT_LABELS[segment_type])

    # Validate duration against SkipDB's per-type bounds
    max_secs = skipdb.MAX_SEGMENT_SECS[segment_type]
    if duration < skipdb.MIN_SEGMENT_SECS:
        xbmc.executebuiltin(
            'Notification(SkipDB, Too short — must be at least {:.0f} seconds, 3000)'.format(
                skipdb.MIN_SEGMENT_SECS))
        session.submit_start_sec = None
        return False
    if duration > max_secs:
        xbmc.executebuiltin(
            'Notification(SkipDB, Too long — {} max is {:.0f} minutes, 3000)'.format(
                type_label, max_secs / 60.0))
        session.submit_start_sec = None
        return False

    # Confirm
    confirm = xbmcgui.Dialog().yesno(
        'SkipDB',
        'Submit {}: {:.0f}s \u2192 {:.0f}s ({:.0f}s)?'.format(type_label, start, end, duration),
    )
    if not confirm:
        session.submit_start_sec = None
        xbmc.log('[SkipDB] User cancelled submission', xbmc.LOGINFO)
        return False

    # Submit
    success, msg = skipdb.submit_segment(
        imdb_id=media_ids.get('lookup_imdb_id'),
        season=media_ids.get('season'),
        episode=media_ids.get('episode'),
        is_movie=media_ids.get('is_movie', False),
        segment=segment_type,
        start_sec=start,
        end_sec=end,
        video_duration_ms=media_ids.get('duration_ms'),
    )
    session.submit_start_sec = None
    if success:
        xbmc.executebuiltin('Notification(SkipDB, {}, 3000)'.format(msg))
        session.submitted_types.add(segment_type)
        return True  # invalidate cache
    xbmc.executebuiltin('Notification(SkipDB, {}, 4000)'.format(msg))
    return False


# ── Main service loop ─────────────────────────────────────────────────────

def _run_service() -> None:
    monitor = SkipDBMonitor()
    player = SkipDBPlayer()
    session = PlaybackSession()

    xbmc.log('[SkipDB] Service started', xbmc.LOGINFO)

    while not monitor.abortRequested():
        if monitor.waitForAbort(1.0):
            break

        # ── API key test button (settings) ──
        if _fresh_bool('test_api_key_now'):
            try:
                xbmcaddon.Addon(_ADDON_ID).setSetting('test_api_key_now', 'false')
            except Exception:
                pass
            _run_api_key_test()

        # ── Anonymous API key button (settings) ──
        if _fresh_bool('get_anonymous_key_now'):
            try:
                xbmcaddon.Addon(_ADDON_ID).setSetting('get_anonymous_key_now', 'false')
            except Exception:
                pass
            _run_get_anonymous_key()

        if not player.playback_started:
            session.reset()
            continue

        # skip movies that do not look like tv; player decides
        if not player.is_tv_content:
            continue

        filename = player.filename
        if not filename:
            continue

        # New file — reset everything
        if filename != session.current_file:
            session.reset()
            session.current_file = filename
            xbmc.log('[SkipDB] Reset segment tracking for file: {}'.format(filename),
                     xbmc.LOGINFO)

        _debug_osd('Monitoring: {}'.format(filename[-40:]))

        # ── Fetch media IDs (cached) ──
        if session.media_ids is None:
            session.media_ids = player.get_media_ids()
            xbmc.log('[SkipDB] Media IDs: lookup_imdb={} imdb={} S{}E{} movie={}'.format(
                session.media_ids.get('lookup_imdb_id'), session.media_ids.get('imdb_id'),
                session.media_ids.get('season'), session.media_ids.get('episode'),
                session.media_ids.get('is_movie', False)), xbmc.LOGINFO)
        media_ids = session.media_ids
        imdb = media_ids.get('lookup_imdb_id')
        m_season = media_ids.get('season')
        m_episode = media_ids.get('episode')
        m_movie = media_ids.get('is_movie', False)

        skipdb_on = _fresh_bool('skipdb_enabled')
        if _debug_logging():
            _raw = xbmcaddon.Addon(_ADDON_ID).getSetting('skipdb_enabled')
            xbmc.log('[SkipDB] skipdb_enabled raw={!r} lookups_on={}'.format(
                _raw, skipdb_on), xbmc.LOGINFO)

        # ── Fetch segments (cached) ──
        all_segments = {}
        if skipdb_on and imdb:
            if session.all_segments is None:
                session.all_segments = skipdb.query_all_segments(
                    imdb_id=imdb,
                    season=m_season, episode=m_episode, is_movie=m_movie,
                    duration_ms=media_ids.get('duration_ms'),
                )
            all_segments = session.all_segments or {}

        if all_segments and _debug_logging():
            xbmc.log('[SkipDB] API returned segments: {}'.format(
                list(all_segments.keys())), xbmc.LOGINFO)
            for seg_type, segs in all_segments.items():
                xbmc.log('[SkipDB] {} segments: {}'.format(seg_type, len(segs)),
                         xbmc.LOGINFO)

        # ── Process skip buttons ──
        enabled_segments = _collect_enabled_segments(all_segments)
        if _debug_logging():
            xbmc.log('[SkipDB] Total enabled segments to process: {}'.format(
                len(enabled_segments)), xbmc.LOGINFO)

        for seg_idx, segment in enumerate(enabled_segments):
            result = _handle_segment(
                segment, seg_idx, player, monitor, session, filename)
            if result == 'break':
                break

        # ── Pause-to-submit ──
        cache_dirty = _handle_submit_tick(
            session, player, monitor, all_segments, media_ids)
        if cache_dirty:
            session.all_segments = None

    xbmc.log('[SkipDB] Service stopped', xbmc.LOGINFO)


# ── Segment button timing ────────────────────────────────────────────────

def _should_show_segment_button(processed_segments: Dict[str, Dict[str, Any]], segment_key: str, current_time: float,
                                segment_start: float, segment_end: float, margin: float = 0.5) -> bool:
    """
    Show the skip button once per segment entry.

    If playback exits a segment and later re-enters it, including by seeking into
    the middle of the segment, the next entry gets a fresh 5 second overlay.
    """
    state = processed_segments.setdefault(segment_key, {
        'inside': False,
        'shown_for_entry': False,
        'last_time': None,
    })

    inside_segment = segment_start <= current_time < (segment_end - margin)
    previous_time = state.get('last_time')

    if not inside_segment:
        state['inside'] = False
        state['shown_for_entry'] = False
        state['last_time'] = current_time
        return False

    reentered = (not state['inside'])
    if previous_time is not None and current_time + margin < previous_time:
        reentered = True

    if reentered:
        if _debug_logging():
            xbmc.log('[SkipDB] Entry detected for {} at {:.1f}s'.format(
                segment_key, current_time), xbmc.LOGINFO)
        state['shown_for_entry'] = False

    state['inside'] = True
    state['last_time'] = current_time

    if state['shown_for_entry']:
        return False

    state['shown_for_entry'] = True
    return True

if __name__ == '__main__':
    _run_service()
