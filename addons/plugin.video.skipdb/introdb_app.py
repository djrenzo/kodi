# SPDX-License-Identifier: GPL-2.0-or-later
#
# IntroDB (introdb.app) API client, used as a second fallback for segment types that
# neither SkipDB nor TheIntroDB have data for. Reads are open; matched by IMDb id
# (the show's id + season/episode for TV, is_movie=true for movies).
import json
import threading
import time
import xbmc
import xbmcaddon
from typing import Optional, Dict, Any, Union

from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

ADDON = xbmcaddon.Addon()
_ADDON_ID = ADDON.getAddonInfo('id')

API_BASE = 'https://api.introdb.app'
USER_AGENT = 'SkipDB Kodi Addon/1.0 (IntroDB fallback)'
MIN_REQUEST_GAP = 0.5
_last_request_time = 0.0
_rate_limit_until = 0.0
_rate_limit_lock = threading.Lock()

# IntroDB calls end credits "outro". Its "post_credits" is a scene worth watching, not skipping, so it is ignored.
API_TO_LOCAL = {'intro': 'intro', 'recap': 'recap', 'outro': 'credits'}


def _fresh_setting(key: str) -> str:
    try:
        return xbmcaddon.Addon(_ADDON_ID).getSetting(key)
    except Exception:
        return ADDON.getSetting(key)


def _debug_logging() -> bool:
    return _fresh_setting('debug_logging') == 'true'


def _is_enabled() -> bool:
    return _fresh_setting('introdb_app_fallback') == 'true'


def _wait_rate_limit() -> bool:
    global _last_request_time
    with _rate_limit_lock:
        now = time.time()
        if now < _rate_limit_until:
            xbmc.log('[SkipDB] IntroDB rate-limited until {:.0f}'.format(_rate_limit_until), xbmc.LOGINFO)
            return False
        gap = now - _last_request_time
        if gap < MIN_REQUEST_GAP:
            time.sleep(MIN_REQUEST_GAP - gap)
        _last_request_time = time.time()
    return True


def _do_request(url: str) -> Optional[Dict[str, Any]]:
    global _rate_limit_until
    req = Request(url)
    req.add_header('Accept', 'application/json')
    req.add_header('User-Agent', USER_AGENT)
    try:
        body = urlopen(req, timeout=8).read().decode('utf-8')
        if _debug_logging():
            xbmc.log('[SkipDB] IntroDB response: {}'.format(body[:500]), xbmc.LOGINFO)
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except HTTPError as e:
        if e.code == 429:
            retry = 60
            val = e.headers.get('Retry-After') if e.headers else None
            if val:
                try:
                    retry = int(val)
                except ValueError:
                    pass
            with _rate_limit_lock:
                _rate_limit_until = time.time() + retry
            xbmc.log('[SkipDB] IntroDB 429 rate limited for {}s'.format(retry), xbmc.LOGWARNING)
        elif e.code == 404:
            xbmc.log('[SkipDB] IntroDB 404: not in database', xbmc.LOGINFO)
        else:
            xbmc.log('[SkipDB] IntroDB HTTP {}'.format(e.code), xbmc.LOGWARNING)
        return None
    except URLError as e:
        xbmc.log('[SkipDB] IntroDB network error: {}'.format(e.reason), xbmc.LOGWARNING)
        return None
    except Exception as e:
        xbmc.log('[SkipDB] IntroDB request failed: {}'.format(e), xbmc.LOGERROR)
        return None


def _build_url(imdb_id: Optional[str], season: Optional[Union[str, int]], episode: Optional[Union[str, int]],
               is_movie: bool) -> Optional[str]:
    imdb = str(imdb_id or '').strip()
    if not imdb.startswith('tt'):
        return None
    if is_movie:
        return '{}/segments?{}'.format(API_BASE, urlencode({'imdb_id': imdb, 'is_movie': 'true'}))
    try:
        s, e = int(season), int(episode)
    except (TypeError, ValueError):
        return None
    if s < 1 or e < 1:
        return None
    return '{}/segments?{}'.format(API_BASE, urlencode({'imdb_id': imdb, 'season': s, 'episode': e}))


def query_all_segments(imdb_id: Optional[str] = None, season: Optional[Union[str, int]] = None,
                       episode: Optional[Union[str, int]] = None, is_movie: bool = False) -> Dict[str, Any]:
    """Return {'intro'|'recap'|'credits': [segment]} for everything IntroDB has."""
    if not _is_enabled():
        return {}

    url = _build_url(imdb_id, season, episode, is_movie)
    if not url:
        xbmc.log('[SkipDB] IntroDB: need an IMDb tt… id, plus season/episode for TV', xbmc.LOGINFO)
        return {}

    xbmc.log('[SkipDB] IntroDB query all segments: {}'.format(url), xbmc.LOGINFO)
    if not _wait_rate_limit():
        return {}

    data = _do_request(url)
    if not data or 'error' in data:
        if data:
            xbmc.log('[SkipDB] IntroDB error: {}'.format(data['error']), xbmc.LOGINFO)
        return {}

    all_segments: Dict[str, Any] = {}
    for api_type, local_type in API_TO_LOCAL.items():
        seg = data.get(api_type)
        if not isinstance(seg, dict):
            continue
        start = seg.get('start_ms')
        end = seg.get('end_ms')
        if start is None:
            start = 0
        if end is None or end <= start:
            continue
        all_segments[local_type] = [{
            'start': start / 1000.0,
            'end': end / 1000.0,
            'score': float(seg.get('confidence') if seg.get('confidence') is not None else 0.5),
            'type': local_type,
            'source': 'introdb_app',
        }]
        if _debug_logging():
            xbmc.log('[SkipDB] IntroDB {}: {:.1f}s -> {:.1f}s'.format(local_type, start / 1000.0, end / 1000.0),
                     xbmc.LOGINFO)

    return all_segments
