import base64
import json
import os
import re
import sys
from typing import List, Optional, TypedDict
from urllib.parse import quote_plus, urlencode

import xbmc
import xbmcaddon
import xbmcvfs
import xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
# Only plugin invocations get these arguments; the background service imports this
# module too (e.g. via torbox_supabase) and has none.
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
BASE_URL = sys.argv[0] if sys.argv else ''
MAX_ACCOUNTS = 5
APP_NAME = 'TorBox'

PROVIDER_SETTING_AIOSTREAMS_URL = 'aiostreams_url'
PROVIDER_SETTING_TMDB_KEY = 'tmdb_key'
PROVIDER_SETTING_WYZIE_KEY = 'wyzie_key'

OVERRIDES_FILE = os.path.join(PROFILE_PATH, 'overrides.json')

TOP_MOVIES_URL = "https://cinemeta-catalogs.strem.io/top/catalog/{media_type}/top"
SERIES_URL = "https://v3-cinemeta.strem.io/meta/series/{imdb_id}.json"

VIDEO_EXTS = {
    '.mkv', '.mp4', '.avi', '.mov', '.m4v', '.ts', '.m2ts', '.wmv', '.flv', '.webm',
    '.ogv', '.divx', '.mpg', '.mpeg', '.m2v', '.vob', '.strm'
}
SKIP_EXTS = {
    '.nfo', '.jpg', '.jpeg', '.png', '.gif', '.tbn', '.xml', '.srt', '.ass', '.ssa',
    '.sub', '.idx', '.vtt'
}
VIDEO_MIMETYPES = {
    '.mkv': 'video/x-matroska',
    '.mp4': 'video/mp4',
    '.avi': 'video/x-msvideo',
    '.ts': 'video/mp2t',
    '.mov': 'video/quicktime',
    '.webm': 'video/webm',
}

_QUALITY_TAGS = re.compile(
    r'\b('
    r'2160p|1080p|1080i|720p|576p|480p|4K|UHD|HD|SD|'
    r'BluRay|BDRip|BRRip|WEB[-.]?DL|WEBRip|WEB|'
    r'HDTV|DVDRip|DVDScr|DVD|PDTV|SDTV|HDCAM|CAM|TS|'
    r'x264|x265|H\.?264|H\.?265|HEVC|AVC|XviD|DivX|'
    r'AAC[\d.]*|AC3|DTS|DD[\d.]*|TrueHD|Atmos|EAC3|DDP[\d.]*|'
    r'10bit|8bit|HDR|HDR10|DV|DoVi|'
    r'AMZN|NF|DSNP|HMAX|ATVP|PCOK|iP|'
    r'PROPER|REPACK|EXTENDED|THEATRICAL|UNRATED|DIRECTORS\.CUT|'
    r'MULTI|MULTi|FRENCH|GERMAN|SPANISH|ITALIAN|'
    r'\[TR-EN\]|\[EN\]|\[rartv\]'
    r')\b',
    re.IGNORECASE,
)
_MISSING_PROVIDER_SETTING_NOTIFIED = set()


class Account(TypedDict):
    index: int
    name: str
    url: str
    username: str
    password: str


class WebDavItem(TypedDict):
    name: str
    full_url: str
    path: str
    is_collection: bool
    size: int


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[plugin.video.torbox] {}'.format(msg), level)


def build_url(params):
    return '{}?{}'.format(BASE_URL, urlencode(params))


def get_required_setting(setting_id, display_name, notify=True):
    value = ADDON.getSettingString(setting_id).strip()
    if value:
        return value

    log('{} is not set'.format(setting_id), xbmc.LOGWARNING)

    if notify and setting_id not in _MISSING_PROVIDER_SETTING_NOTIFIED:
        xbmcgui.Dialog().notification(
            APP_NAME,
            '{} is not configured. Set it in Management > Configure provider keys.'.format(display_name),
            xbmcgui.NOTIFICATION_WARNING,
            4500,
        )
        _MISSING_PROVIDER_SETTING_NOTIFIED.add(setting_id)

    return ''


def get_aiostreams_url(notify=True):
    return get_required_setting(PROVIDER_SETTING_AIOSTREAMS_URL, 'AIOStreams URL', notify=notify)


def get_tmdb_key(notify=True):
    return get_required_setting(PROVIDER_SETTING_TMDB_KEY, 'TMDB key', notify=notify)


def get_wyzie_key(notify=True):
    return get_required_setting(PROVIDER_SETTING_WYZIE_KEY, 'Wyzie key', notify=notify)


def get_params():
    params = {}
    query = sys.argv[2].lstrip('?')
    if query:
        from urllib.parse import unquote_plus

        for part in query.split('&'):
            if '=' in part:
                key, value = part.split('=', 1)
                params[key] = unquote_plus(value)
    return params

def get_top_catalog(skip: int, media_type):
    from torbox_http import fetch_json
    if not media_type in ['movie', 'series']:
        raise ValueError('Invalid media_type: {}'.format(media_type))

    base_url = TOP_MOVIES_URL.format(media_type=media_type)
    if skip < 0:
        return []
    elif skip == 0:
        url = f"{base_url}.json"
    else:
        url = f"{base_url}/skip={skip}.json"

    data = fetch_json(url)

    if data:
        return data.get('metas', [])
    
    return []


def search_streams(media_type, imdb_id):
    from torbox_http import fetch_json
    
    imdb_id = (str(imdb_id) or '').strip()
    if not imdb_id:
        return []

    aiostreams_url = get_aiostreams_url(notify=True)
    if not aiostreams_url:
        log('search_streams: aiostreams_url is empty', xbmc.LOGWARNING)
        return []

    try:
        url_stream = aiostreams_url.format(media_type=media_type, imdb_id=imdb_id)
    except Exception as exc:
        log('search_streams: invalid aiostreams_url template: {}'.format(exc), xbmc.LOGWARNING)
        return []

    data = fetch_json(url_stream)
    if data:
        return data.get('streams', [])

    return []


def load_overrides():
    if not xbmcvfs.exists(OVERRIDES_FILE):
        return {}

    try:
        with xbmcvfs.File(OVERRIDES_FILE, 'r') as f:
            return json.loads(f.read())
    except Exception as exc:
        log('Failed to load overrides: {}'.format(exc), xbmc.LOGWARNING)
        return {}


def save_overrides(data):
    if not xbmcvfs.exists(PROFILE_PATH):
        xbmcvfs.mkdirs(PROFILE_PATH)

    try:
        with xbmcvfs.File(OVERRIDES_FILE, 'w') as f:
            f.write(json.dumps(data, indent=2))
    except Exception as exc:
        log('Failed to save overrides: {}'.format(exc), xbmc.LOGWARNING)


def extract_episode_info(filename):
    patterns = [
        r'[Ss](\d{1,2})[.\-_ ]?[Ee](\d{1,3})',
        r'(\d{1,2})[xX](\d{2,3})',
    ]

    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return int(match.group(1)), int(match.group(2))

    return None, None


def extract_bare_episode(filename):
    """Episode number from names that carry no season, e.g. 'Show.2019.E02.1080p' or 'Show - E21 [BD]'."""
    match = re.search(r'(?<![A-Za-z0-9])(?:Episode[ ._-]?|EP?)(\d{1,3})(?!\d)', filename, re.IGNORECASE)
    return int(match.group(1)) if match else None


def guess_season(name):
    """Season hinted by a folder name ('S01', 'Season 2'), or None."""
    match = re.search(r'\b(?:S|Season[ ._-]?)(\d{1,2})\b', name or '', re.IGNORECASE)
    return int(match.group(1)) if match else None


def get_accounts() -> List[Account]:
    accounts: List[Account] = []
    for idx in range(1, MAX_ACCOUNTS + 1):
        if not ADDON.getSettingBool('account{}_enabled'.format(idx)):
            continue

        name = ADDON.getSettingString('account{}_name'.format(idx))
        url = ADDON.getSettingString('account{}_url'.format(idx)).rstrip('/')
        username = ADDON.getSettingString('account{}_username'.format(idx))
        password = ADDON.getSettingString('account{}_password'.format(idx))

        if url and username and password:
            accounts.append(
                {
                    'index': idx,
                    'name': name or 'Account {}'.format(idx),
                    'url': url,
                    'username': username,
                    'password': password,
                }
            )
    return accounts


def get_account(index: int) -> Optional[Account]:
    return next((acc for acc in get_accounts() if acc['index'] == index), None)


def make_auth_header(username, password):
    encoded = base64.b64encode('{}:{}'.format(username, password).encode('utf-8')).decode('utf-8')
    return 'Basic {}'.format(encoded)


def save_credentials(account_id, url, username, password):
    ADDON.setSettingString('account{}_url'.format(account_id), url)
    ADDON.setSettingString('account{}_username'.format(account_id), username)
    ADDON.setSettingString('account{}_password'.format(account_id), password)
    ADDON.setSettingBool('account{}_enabled'.format(account_id), True)
