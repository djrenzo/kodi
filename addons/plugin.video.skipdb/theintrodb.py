# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 TheIntroDB (original plugin.video.tidb)
#
# TheIntroDB API client, used as a fallback for segment types SkipDB has no data for.
import threading
import json
import time
import xbmc
import xbmcaddon
from typing import Optional, Dict, Any, Tuple, List, Union

from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ADDON = xbmcaddon.Addon()
_ADDON_ID = ADDON.getAddonInfo('id')

API_BASE = 'https://api.theintrodb.org/v3'
MIN_REQUEST_GAP = 0.4  # small gap between requests
_last_request_time = 0.0
_rate_limit_until = 0.0
_rate_limit_lock = threading.Lock()


def _debug_logging() -> bool:
    return ADDON.getSetting('debug_logging') == 'true'


def _log_resp(body: str) -> None:
    if not _debug_logging():
        return
    snippet = body[:500] if len(body) > 500 else body
    xbmc.log('[SkipDB] TheIntroDB response: {}'.format(snippet), xbmc.LOGINFO)


def _get_api_key() -> str:
    return (ADDON.getSetting('introdb_api_key') or '').strip()


def _is_enabled() -> bool:
    try:
        return xbmcaddon.Addon(_ADDON_ID).getSetting('theintrodb_fallback') == 'true'
    except Exception:
        return ADDON.getSetting('theintrodb_fallback') == 'true'


def _wait_rate_limit() -> bool:
    global _last_request_time
    with _rate_limit_lock:
        now = time.time()
        if now < _rate_limit_until:
            xbmc.log('[SkipDB] TheIntroDB rate-limited until {:.0f}'.format(
                _rate_limit_until), xbmc.LOGINFO)
            return False
        gap = now - _last_request_time
        if gap < MIN_REQUEST_GAP:
            time.sleep(MIN_REQUEST_GAP - gap)
        _last_request_time = time.time()
    return True


def _do_request(url: str, api_key: str) -> Optional[Dict[str, Any]]:
    global _rate_limit_until
    req = Request(url)
    req.add_header('Accept', 'application/json')
    req.add_header('User-Agent', 'SkipDB Kodi Addon/1.0 (TheIntroDB fallback)')
    if api_key:
        req.add_header('Authorization', 'Bearer {}'.format(api_key))

    try:
        resp = urlopen(req, timeout=8)
        body = resp.read().decode('utf-8')
        data = json.loads(body)
        _log_resp(body)
        return data
    except HTTPError as e:
        if e.code == 429:
            retry = 300
            for header in ('X-UsageLimit-Reset', 'X-RateLimit-Reset', 'Retry-After'):
                val = e.headers.get(header)
                if val:
                    try:
                        retry = int(val)
                    except ValueError:
                        pass
                    break
            with _rate_limit_lock:
                _rate_limit_until = time.time() + retry
            xbmc.log('[SkipDB] TheIntroDB 429 rate limited for {}s'.format(retry),
                     xbmc.LOGWARNING)
        elif e.code == 404:
            xbmc.log('[SkipDB] TheIntroDB 404: not in database', xbmc.LOGINFO)
        else:
            xbmc.log('[SkipDB] TheIntroDB HTTP {}'.format(e.code), xbmc.LOGWARNING)
        return None
    except URLError as e:
        xbmc.log('[SkipDB] TheIntroDB network error: {}'.format(e.reason),
                 xbmc.LOGWARNING)
        return None
    except Exception as e:
        xbmc.log('[SkipDB] TheIntroDB request failed: {}'.format(e),
                 xbmc.LOGERROR)
        return None


def _pick_best_segments_all_types(segments: List[Dict[str, Any]], segment_type: str) -> List[Dict[str, Any]]:
    """Pick the best segment(s) for a given type, handling multiple segments."""
    if not segments:
        return []

    valid_segments = []
    for seg_idx, seg in enumerate(segments):
        if not isinstance(seg, dict):
            xbmc.log('[SkipDB] TheIntroDB: Skipping {} segment {}: not a dict'.format(segment_type, seg_idx), xbmc.LOGINFO)
            continue
        
        start = seg.get('start_ms')
        end = seg.get('end_ms')
        
        if ADDON.getSetting('debug_logging') == 'true':
            xbmc.log('[SkipDB] TheIntroDB: Processing {} segment {}: start_ms={}, end_ms={}'.format(segment_type, seg_idx, start, end), xbmc.LOGINFO)
        
        # Handle different segment type requirements
        if segment_type == 'intro' or segment_type == 'recap':
            # Intro/Recap: start optional (can be null), end required
            if end is None:
                if ADDON.getSetting('debug_logging') == 'true':
                    xbmc.log('[SkipDB] TheIntroDB: Skipping {} segment {}: end is None'.format(segment_type, seg_idx), xbmc.LOGINFO)
                continue
            if start is None:
                start = 0
        elif segment_type == 'credits' or segment_type == 'preview':
            # Credits/Preview: start required, end optional (null = end of media)
            if start is None:
                if ADDON.getSetting('debug_logging') == 'true':
                    xbmc.log('[SkipDB] TheIntroDB: Skipping {} segment {}: start is None'.format(segment_type, seg_idx), xbmc.LOGINFO)
                continue
            # end can be null (means end of media)
        
        if end is not None and end <= start:
            if ADDON.getSetting('debug_logging') == 'true':
                xbmc.log('[SkipDB] TheIntroDB: Skipping {} segment {}: end <= start ({} <= {})'.format(segment_type, seg_idx, end, start), xbmc.LOGINFO)
            continue
            
        conf = seg.get('confidence') if seg.get('confidence') is not None else 0.5
        count = seg.get('submission_count', 1)
        score = float(conf) + count * 0.001
        
        if ADDON.getSetting('debug_logging') == 'true':
            xbmc.log('[SkipDB] TheIntroDB: Valid {} segment {}: start={}, end={}, score={:.3f}'.format(segment_type, seg_idx, start, end, score), xbmc.LOGINFO)
        
        valid_segments.append({
            'start_ms': start,
            'end_ms': end,
            'score': score,
            'confidence': conf,
            'submission_count': count
        })
    
    if ADDON.getSetting('debug_logging') == 'true':
        xbmc.log('[SkipDB] TheIntroDB: {} valid {} segments found'.format(len(valid_segments), segment_type), xbmc.LOGINFO)
    
    # Sort by score (highest first) and return top segments
    valid_segments.sort(key=lambda x: x['score'], reverse=True)
    
    # Convert to seconds and return
    result_segments = []
    for seg in valid_segments:
        start_sec = seg['start_ms'] / 1000.0 if seg['start_ms'] is not None else None
        end_sec = seg['end_ms'] / 1000.0 if seg['end_ms'] is not None else None
        result_segments.append({
            'start': start_sec,
            'end': end_sec,
            'score': seg['score'],
            'type': segment_type,
            'source': 'theintrodb',
        })
    
    if ADDON.getSetting('debug_logging') == 'true':
        xbmc.log('[SkipDB] TheIntroDB: Returning {} processed {} segments'.format(len(result_segments), segment_type), xbmc.LOGINFO)
    return result_segments


def _normalize_imdb(imdb_id: Optional[str]) -> Optional[str]:
    if not imdb_id:
        return None
    s = str(imdb_id).strip()
    if not s.startswith('tt'):
        return None
    return s


def _valid_tmdb(tmdb_id: Optional[Union[str, int]]) -> bool:
    try:
        return int(str(tmdb_id)) > 0
    except (ValueError, TypeError):
        return False


def _episode_nums(season: Optional[Union[str, int]], episode: Optional[Union[str, int]]) -> Tuple[Optional[int], Optional[int]]:
    try:
        s = int(season)
        e = int(episode)
        return s, e
    except (TypeError, ValueError):
        return None, None


def _build_url(tmdb_id: Optional[Union[str, int]], imdb_id: Optional[str], season: Optional[Union[str, int]], episode: Optional[Union[str, int]], is_movie: bool, duration_ms: Optional[Union[str, int]] = None) -> Tuple[Optional[str], Optional[str]]:
    # prefer tmdb; if missing use imdb (api matches show/episode)
    duration_q = ''
    try:
        if duration_ms is not None:
            dur_int = int(duration_ms)
            if dur_int > 0:
                duration_q = '&duration_ms={}'.format(dur_int)
    except (TypeError, ValueError):
        duration_q = ''

    if tmdb_id and _valid_tmdb(tmdb_id):
        tid = str(tmdb_id).strip()
        if is_movie:
            return '{}/media?tmdb_id={}{}'.format(API_BASE, tid, duration_q), 'tmdb'
        s, e = _episode_nums(season, episode)
        if s is None or e is None or s <= 0 or e <= 0:
            return None, None
        return (
            '{}/media?tmdb_id={}&season={}&episode={}{}'.format(API_BASE, tid, s, e, duration_q),
            'tmdb',
        )

    imdb = _normalize_imdb(imdb_id)
    if not imdb:
        return None, None

    if is_movie:
        return '{}/media?imdb_id={}{}'.format(API_BASE, imdb, duration_q), 'imdb'

    s, e = _episode_nums(season, episode)
    if s is None or e is None or s <= 0 or e <= 0:
        return None, None
    return '{}/media?imdb_id={}&season={}&episode={}{}'.format(
        API_BASE, imdb, s, e, duration_q), 'imdb'


def query_all_segments(tmdb_id: Optional[Union[str, int]] = None, imdb_id: Optional[str] = None, season: Optional[Union[str, int]] = None, episode: Optional[Union[str, int]] = None, is_movie: bool = False, duration_ms: Optional[Union[str, int]] = None) -> Dict[str, Any]:
    # returns dict with all segment types and their segments
    if not _is_enabled():
        return {}

    url, mode = _build_url(tmdb_id, imdb_id, season, episode, is_movie, duration_ms=duration_ms)
    if not url:
        if tmdb_id or imdb_id:
            xbmc.log(
                '[SkipDB] TheIntroDB: need TMDB id, or IMDb tt… id with season/episode for TV',
                xbmc.LOGINFO,
            )
        else:
            xbmc.log('[SkipDB] TheIntroDB: no TMDB or IMDb id', xbmc.LOGINFO)
        return {}

    xbmc.log('[SkipDB] TheIntroDB query all segments ({}): {}'.format(mode, url), xbmc.LOGINFO)

    if not _wait_rate_limit():
        return {}

    api_key = _get_api_key()
    data = _do_request(url, api_key)
    if not data:
        return {}

    if 'error' in data:
        xbmc.log('[SkipDB] TheIntroDB error: {}'.format(data['error']), xbmc.LOGINFO)
        return {}

    # Process all segment types
    all_segments = {}
    
    # Debug: Log what the API actually returned (only if debug logging is enabled)
    if ADDON.getSetting('debug_logging') == 'true':
        xbmc.log('[SkipDB] TheIntroDB: API response keys: {}'.format(list(data.keys())), xbmc.LOGINFO)
        xbmc.log('[SkipDB] TheIntroDB: Full API response (first 500 chars): {}'.format(str(data)[:500]), xbmc.LOGINFO)
        for key in data.keys():
            if key in ['intro', 'recap', 'credits', 'preview']:
                xbmc.log('[SkipDB] TheIntroDB: API {} raw data: {}'.format(key, len(data.get(key, []))), xbmc.LOGINFO)
    
    segment_types = ['intro', 'recap', 'credits', 'preview']
    for seg_type in segment_types:
        raw_segments = data.get(seg_type, [])
        if ADDON.getSetting('debug_logging') == 'true':
            xbmc.log('[SkipDB] TheIntroDB: Processing {}: {} raw segments'.format(seg_type, len(raw_segments)), xbmc.LOGINFO)
        segments = _pick_best_segments_all_types(raw_segments, seg_type)
        if segments:
            all_segments[seg_type] = segments
            if ADDON.getSetting('debug_logging') == 'true':
                xbmc.log('[SkipDB] TheIntroDB {}: {} valid segments'.format(seg_type, len(segments)), xbmc.LOGINFO)
        else:
            if ADDON.getSetting('debug_logging') == 'true':
                xbmc.log('[SkipDB] TheIntroDB {}: no valid segments'.format(seg_type), xbmc.LOGINFO)
    
    if ADDON.getSetting('debug_logging') == 'true':
        xbmc.log('[SkipDB] TheIntroDB: Final segments dict: {}'.format(list(all_segments.keys())), xbmc.LOGINFO)
    return all_segments
