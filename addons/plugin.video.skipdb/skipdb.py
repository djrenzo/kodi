# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 TheIntroDB (original plugin.video.tidb)
#
# SkipDB API client — https://skipdb.tv/docs
# Segments are looked up by IMDb id (the show's id + season/episode for TV).
import threading
import json
import time
import xbmc
import xbmcaddon
from typing import Optional, Dict, Any, Tuple, Union

from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

ADDON = xbmcaddon.Addon()
_ADDON_ID = ADDON.getAddonInfo('id')

API_BASE = 'https://api.skipdb.tv'
USER_AGENT = 'SkipDB Kodi Addon/1.0'
MIN_REQUEST_GAP = 0.5  # reads are limited to 120/min
_last_request_time = 0.0
_rate_limit_until = 0.0
_rate_limit_lock = threading.Lock()

# SkipDB calls end credits "outro"; the addon (settings, strings, overlay) keeps calling them "credits".
API_TO_LOCAL = {'intro': 'intro', 'recap': 'recap', 'outro': 'credits', 'preview': 'preview'}
LOCAL_TO_API = {local: api for api, local in API_TO_LOCAL.items()}

# Max segment length per type, from the SkipDB docs (min is 5s for all).
MIN_SEGMENT_SECS = 5.0
MAX_SEGMENT_SECS = {'intro': 300.0, 'recap': 300.0, 'credits': 900.0, 'preview': 900.0}

ADJUST_MODES = ('conservative', 'greedy', 'none')


def _fresh_setting(key: str) -> str:
    try:
        return xbmcaddon.Addon(_ADDON_ID).getSetting(key)
    except Exception:
        return ADDON.getSetting(key)


def _debug_logging() -> bool:
    return _fresh_setting('debug_logging') == 'true'


def _log_resp(body: str) -> None:
    if not _debug_logging():
        return
    snippet = body[:500] if len(body) > 500 else body
    xbmc.log('[SkipDB] SkipDB response: {}'.format(snippet), xbmc.LOGINFO)


def _get_api_key() -> str:
    return (_fresh_setting('skipdb_api_key') or '').strip()


def _is_enabled() -> bool:
    return _fresh_setting('skipdb_enabled') == 'true'


def _adjust_mode() -> str:
    try:
        return ADJUST_MODES[int(_fresh_setting('duration_adjust') or 0)]
    except (ValueError, IndexError):
        return ADJUST_MODES[0]


def _new_request(url: str, api_key: str = '', data: Optional[bytes] = None, method: str = 'GET') -> Request:
    req = Request(url, data=data, method=method)
    req.add_header('Accept', 'application/json')
    req.add_header('User-Agent', USER_AGENT)
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    if api_key:
        req.add_header('Authorization', 'Bearer {}'.format(api_key))
    return req


def _error_body(e: HTTPError) -> Dict[str, Any]:
    # HTTPError bodies can only be read once; cache the parsed JSON on the exception
    if not hasattr(e, '_skipdb_body'):
        try:
            data = json.loads(e.read().decode('utf-8'))
            e._skipdb_body = data if isinstance(data, dict) else {}
        except Exception:
            e._skipdb_body = {}
    return e._skipdb_body


def _error_message(e: HTTPError) -> str:
    try:
        err_data = _error_body(e)
        msg = err_data.get('error') or 'HTTP {}'.format(e.code)
        issues = err_data.get('issues')
        if isinstance(issues, list) and issues:
            first = issues[0]
            detail = first.get('message') if isinstance(first, dict) else str(first)
            if detail:
                msg = '{} ({})'.format(msg, detail)
        return msg
    except Exception:
        return 'HTTP {}'.format(e.code)


def _note_rate_limit(e: HTTPError) -> None:
    global _rate_limit_until
    retry = 60
    for header in ('Retry-After', 'X-RateLimit-Reset'):
        val = e.headers.get(header) if e.headers else None
        if val:
            try:
                retry = int(val)
            except ValueError:
                pass
            break
    with _rate_limit_lock:
        _rate_limit_until = time.time() + retry
    xbmc.log('[SkipDB] SkipDB 429 rate limited for {}s'.format(retry), xbmc.LOGWARNING)


def test_api_key() -> Tuple[bool, str]:
    """Validate the configured API key.

    SkipDB has no "who am I" endpoint, so this posts an intentionally empty submission:
    a bad key gets 401, a good key gets past auth and fails validation (422/400).
    Nothing is stored either way.
    """
    api_key = _get_api_key()
    if not api_key:
        return False, 'No API key configured.'

    req = _new_request('{}/api/segments'.format(API_BASE), api_key, data=b'{}', method='POST')
    try:
        urlopen(req, timeout=8)
        return True, 'API key is valid.'
    except HTTPError as e:
        if e.code == 401:
            return False, 'Invalid API key (401 Unauthorized).'
        if e.code == 403:
            return False, 'API key rejected (403 Forbidden).'
        if e.code == 429:
            return False, 'Rate limited (429). Try again later.'
        if e.code >= 500:
            return False, 'API server error (HTTP {}). Try again later.'.format(e.code)
        return True, 'API key is valid.'
    except URLError as e:
        return False, 'API unreachable: {}'.format(e.reason)
    except Exception as e:
        return False, 'Request failed: {}'.format(e)


def create_anonymous_key() -> Tuple[Optional[str], str]:
    """Request a new anonymous SkipDB API key (no account needed; cannot vote).

    Returns (key, message); key is None on failure.
    """
    req = _new_request('{}/api/keys/anonymous'.format(API_BASE), data=b'{}', method='POST')
    try:
        resp = urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        key = (data.get('key') or '').strip()
        if not key:
            return None, 'SkipDB did not return a key.'
        return key, data.get('message') or 'Anonymous API key created.'
    except HTTPError as e:
        if e.code == 429:
            return None, 'Too many keys requested from this network. Try again in an hour.'
        return None, _error_message(e)
    except URLError as e:
        return None, 'API unreachable: {}'.format(e.reason)
    except Exception as e:
        return None, 'Request failed: {}'.format(e)


def _wait_rate_limit() -> bool:
    global _last_request_time
    with _rate_limit_lock:
        now = time.time()
        if now < _rate_limit_until:
            xbmc.log('[SkipDB] SkipDB rate-limited until {:.0f}'.format(
                _rate_limit_until), xbmc.LOGINFO)
            return False
        gap = now - _last_request_time
        if gap < MIN_REQUEST_GAP:
            time.sleep(MIN_REQUEST_GAP - gap)
        _last_request_time = time.time()
    return True


def _do_request(url: str) -> Optional[Dict[str, Any]]:
    # reads are open; no need to send the key
    try:
        resp = urlopen(_new_request(url), timeout=8)
        body = resp.read().decode('utf-8')
        data = json.loads(body)
        _log_resp(body)
        return data
    except HTTPError as e:
        if e.code == 429:
            _note_rate_limit(e)
        elif e.code == 404:
            xbmc.log('[SkipDB] SkipDB 404: not in database', xbmc.LOGINFO)
        else:
            xbmc.log('[SkipDB] SkipDB HTTP {}: {}'.format(e.code, _error_message(e)), xbmc.LOGWARNING)
        return None
    except URLError as e:
        xbmc.log('[SkipDB] SkipDB network error: {}'.format(e.reason), xbmc.LOGWARNING)
        return None
    except Exception as e:
        xbmc.log('[SkipDB] SkipDB request failed: {}'.format(e), xbmc.LOGERROR)
        return None


def _normalize_imdb(imdb_id: Optional[str]) -> Optional[str]:
    if not imdb_id:
        return None
    s = str(imdb_id).strip()
    if not s.startswith('tt'):
        return None
    return s


def _episode_nums(season: Optional[Union[str, int]], episode: Optional[Union[str, int]]) -> Tuple[Optional[int], Optional[int]]:
    try:
        s = int(season)
        e = int(episode)
        return s, e
    except (TypeError, ValueError):
        return None, None


def _positive_int(value: Optional[Union[str, int, float]]) -> Optional[int]:
    try:
        v = int(value)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _build_url(imdb_id: Optional[str], season: Optional[Union[str, int]], episode: Optional[Union[str, int]],
               is_movie: bool, duration_ms: Optional[Union[str, int]] = None) -> Optional[str]:
    imdb = _normalize_imdb(imdb_id)
    if not imdb:
        return None

    params: Dict[str, Any] = {'imdb_id': imdb}
    if not is_movie:
        s, e = _episode_nums(season, episode)
        if s is None or e is None or s < 0 or e <= 0:
            return None
        params['season'] = s
        params['episode'] = e

    dur = _positive_int(duration_ms)
    if dur:
        # whole seconds: the API recommends it and it improves CDN cache hits
        params['duration'] = int(round(dur / 1000.0))
    params['adjust'] = _adjust_mode()

    return '{}/api/segments?{}'.format(API_BASE, urlencode(params))


def _parse_segment(api_type: str, seg: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(seg, dict):
        return None
    start = seg.get('start_ms')
    end = seg.get('end_ms')
    if start is None:
        start = 0
    # "0 → 0" is SkipDB's "confirmed: this episode has no such segment" sentinel
    if end is not None and end <= start:
        return None
    if end is None and api_type != 'outro':
        return None

    return {
        'start': start / 1000.0,
        'end': end / 1000.0 if end is not None else None,
        'score': float(seg.get('confidence') if seg.get('confidence') is not None else 0.5),
        'match': seg.get('match') or 'agnostic',
        'type': API_TO_LOCAL[api_type],
    }


def query_all_segments(imdb_id: Optional[str] = None, season: Optional[Union[str, int]] = None,
                       episode: Optional[Union[str, int]] = None, is_movie: bool = False,
                       duration_ms: Optional[Union[str, int]] = None) -> Dict[str, Any]:
    """Return {'intro'|'recap'|'credits'|'preview': [segment]} for everything SkipDB has."""
    if not _is_enabled():
        return {}

    url = _build_url(imdb_id, season, episode, is_movie, duration_ms=duration_ms)
    if not url:
        if imdb_id:
            xbmc.log('[SkipDB] SkipDB: need an IMDb tt… id, plus season/episode for TV', xbmc.LOGINFO)
        else:
            xbmc.log('[SkipDB] SkipDB: no IMDb id (SkipDB only supports IMDb ids)', xbmc.LOGINFO)
        return {}

    xbmc.log('[SkipDB] SkipDB query all segments: {}'.format(url), xbmc.LOGINFO)

    if not _wait_rate_limit():
        return {}

    data = _do_request(url)
    if not data:
        return {}

    if 'error' in data:
        xbmc.log('[SkipDB] SkipDB error: {}'.format(data['error']), xbmc.LOGINFO)
        return {}

    raw_segments = data.get('segments') or {}
    all_segments: Dict[str, Any] = {}
    for api_type, local_type in API_TO_LOCAL.items():
        parsed = _parse_segment(api_type, raw_segments.get(api_type))
        if parsed:
            all_segments[local_type] = [parsed]
            if _debug_logging():
                xbmc.log('[SkipDB] SkipDB {}: {:.1f}s -> {} (match={}, confidence={:.2f})'.format(
                    local_type, parsed['start'],
                    '{:.1f}s'.format(parsed['end']) if parsed['end'] is not None else 'end',
                    parsed['match'], parsed['score']), xbmc.LOGINFO)
        elif _debug_logging():
            xbmc.log('[SkipDB] SkipDB {}: no usable segment'.format(local_type), xbmc.LOGINFO)

    if _debug_logging():
        xbmc.log('[SkipDB] Final segments dict: {}'.format(list(all_segments.keys())), xbmc.LOGINFO)
    return all_segments


def submit_segment(imdb_id: Optional[str] = None, season: Optional[Union[str, int]] = None,
                   episode: Optional[Union[str, int]] = None, is_movie: bool = False,
                   segment: str = 'intro', start_sec: Optional[float] = None, end_sec: Optional[float] = None,
                   video_duration_ms: Optional[Union[str, int]] = None) -> Tuple[bool, str]:
    """Submit a segment to SkipDB. `segment` uses the addon's names (credits = outro).

    Returns (success, message) tuple.
    """
    api_key = _get_api_key()
    if not api_key:
        return False, 'API key required for submissions. Set it in addon settings.'

    imdb = _normalize_imdb(imdb_id)
    if not imdb:
        return False, 'Need an IMDb ID to submit.'

    api_type = LOCAL_TO_API.get(segment)
    if not api_type:
        return False, 'Unknown segment type: {}'.format(segment)

    if start_sec is None:
        return False, 'Segment start is required.'

    if not _wait_rate_limit():
        return False, 'Rate limited. Try again later.'

    payload: Dict[str, Any] = {
        'imdb_id': imdb,
        'segment_type': api_type,
        'start_ms': int(round(float(start_sec) * 1000)),
    }
    if end_sec is not None:
        payload['end_ms'] = int(round(float(end_sec) * 1000))

    if not is_movie:
        s, e = _episode_nums(season, episode)
        if s is None or e is None:
            return False, 'Season and episode are required for TV submissions.'
        payload['season'] = s
        payload['episode'] = e

    dur = _positive_int(video_duration_ms)
    if dur:
        payload['duration_ms'] = dur

    url = '{}/api/segments'.format(API_BASE)
    xbmc.log('[SkipDB] Submitting segment: {} -> {}'.format(url, payload), xbmc.LOGINFO)

    req = _new_request(url, api_key, data=json.dumps(payload).encode('utf-8'), method='POST')
    try:
        resp = urlopen(req, timeout=10)
        resp_body = resp.read().decode('utf-8')
        _log_resp(resp_body)
        data = json.loads(resp_body) if resp_body else {}
        status = data.get('status') or 'pending'
        return True, 'Submitted! Status: {}'.format(status)
    except HTTPError as e:
        if e.code == 429:
            _note_rate_limit(e)
        err_msg = _error_message(e)
        body = _error_body(e)
        if e.code == 409 and (body.get('status') == 'already_approved' or body.get('vote_url')):
            # identical approved segment exists — the data is already there
            return True, 'Already in SkipDB.'
        xbmc.log('[SkipDB] Submit failed: {}'.format(err_msg), xbmc.LOGWARNING)
        return False, err_msg
    except URLError as e:
        xbmc.log('[SkipDB] Submit network error: {}'.format(e.reason), xbmc.LOGWARNING)
        return False, 'Network error: {}'.format(e.reason)
    except Exception as e:
        xbmc.log('[SkipDB] Submit error: {}'.format(e), xbmc.LOGERROR)
        return False, str(e)
