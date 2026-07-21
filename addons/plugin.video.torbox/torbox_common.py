import base64
import json
import os
import re
import sys
from typing import List, Optional, TypedDict
from urllib.parse import urlencode

import xbmc
import xbmcaddon
import xbmcvfs

from torbox_paste import paste_and_show_dialog

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
MAX_ACCOUNTS = 3
APP_NAME = 'TorBox'

OVERRIDES_FILE = os.path.join(PROFILE_PATH, 'overrides.json')

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
_YEAR_RANGE = re.compile(r'\b\d{4}-\d{4}\b')
_YEAR = re.compile(r'\b(19|20)\d{2}\b')
_BRACKETS = re.compile(r'\[.*?\]|\((?!\d{4}\))[^)]*\)')
_DOTS_DASHES = re.compile(r'[._]+')
_MULTI_SPACE = re.compile(r'\s{2,}')


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


def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log('[plugin.video.torbox] {}'.format(msg), level)


def build_url(params):
    return '{}?{}'.format(BASE_URL, urlencode(params))


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


def export_overrides():
    # Build a fresh snapshot so exports are never based on a stale/empty file.
    data = load_overrides()

    if not os.path.exists(PROFILE_PATH):
        os.makedirs(PROFILE_PATH, exist_ok=True)

    export_file = os.path.join(PROFILE_PATH, 'overrides.export.json')
    with open(export_file, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2)
        fh.write('\n')

    # If no overrides exist, upload a minimal valid JSON object instead of an empty file.
    if os.path.getsize(export_file) == 0:
        with open(export_file, 'w', encoding='utf-8') as fh:
            fh.write('{}\n')

    return paste_and_show_dialog(export_file)

def import_overrides():
    """
    Fetches the JSON file from the URL configured in addon settings
    ('library_overrides_path') and saves it locally via save_overrides,
    overwriting any existing local copy.
    """
    import xbmcgui
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    url = ADDON.getSettingString('library_overrides_path').strip()
 
    if not url:
        log('import_overrides: no library_overrides_path configured', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification(
            ADDON.getAddonInfo('name'),
            'No overrides URL configured',
            xbmcgui.NOTIFICATION_WARNING,
        )
        return False
 
    try:
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode('utf-8')
    except (HTTPError, URLError) as exc:
        log('import_overrides: failed to fetch {}: {}'.format(url, exc), xbmc.LOGWARNING)
        xbmcgui.Dialog().notification(
            ADDON.getAddonInfo('name'),
            'Failed to download overrides',
            xbmcgui.NOTIFICATION_ERROR,
        )
        return False
 
    try:
        data = json.loads(raw)
    except ValueError as exc:
        log('import_overrides: invalid JSON from {}: {}'.format(url, exc), xbmc.LOGWARNING)
        xbmcgui.Dialog().notification(
            ADDON.getAddonInfo('name'),
            'Overrides file is not valid JSON',
            xbmcgui.NOTIFICATION_ERROR,
        )
        return False
 
    save_overrides(data)
 
    log('import_overrides: successfully imported overrides from {}'.format(url))
    xbmcgui.Dialog().notification(
        ADDON.getAddonInfo('name'),
        'Overrides imported successfully',
        xbmcgui.NOTIFICATION_INFO,
    )
    return True


def clean_show_name(raw_name):
    value = raw_name

    if value.count('.') >= 2:
        value = _DOTS_DASHES.sub(' ', value)

    year = None
    year_range = _YEAR_RANGE.search(value)
    if year_range:
        year = int(year_range.group().split('-')[0])
        value = value.replace(year_range.group(), '')
    else:
        year_match = _YEAR.search(value)
        if year_match:
            year = int(year_match.group())

    value = _BRACKETS.sub(' ', value)
    value = re.sub(r'\bS\d{1,2}(?:-S\d{1,2})?\b', ' ', value, flags=re.IGNORECASE)
    value = re.sub(r'\bSeason\s+\d{1,2}(?:\s*-\s*\d{1,2})?\b', ' ', value, flags=re.IGNORECASE)
    value = _QUALITY_TAGS.sub(' ', value)
    value = _YEAR.sub(' ', value)
    value = re.sub(r'\s+-\s*\w+$', '', value)
    value = re.sub(r'-\w+$', '', value)
    value = re.sub(r'[+]', ' ', value)
    value = re.sub(r"[^\w\s'\-\.]", ' ', value)
    value = _MULTI_SPACE.sub(' ', value).strip(' -.')

    return value, year


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
