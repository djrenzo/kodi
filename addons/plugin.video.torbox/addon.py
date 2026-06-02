"""
TorBox WebDAV Kodi Plugin v2.0
- Multi-account WebDAV browser
- Direct HTTP/2 playback with injected auth headers (no proxy)
- Full Kodi library integration: TV shows with metadata & artwork
- Automatic folder name cleaning (strips quality tags)
- Manual TVDB/TMDB ID override via overrides.json
"""

import sys
import os
import re
import json
import base64
import xml.etree.ElementTree as ET
from urllib.parse import urlencode, quote, unquote, urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import shutil

ADDON        = xbmcaddon.Addon()
ADDON_ID     = ADDON.getAddonInfo('id')
ADDON_PATH   = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
HANDLE       = int(sys.argv[1])
BASE_URL     = sys.argv[0]

OVERRIDES_FILE = os.path.join(PROFILE_PATH, 'overrides.json')

VIDEO_EXTS    = {'.mkv','.mp4','.avi','.mov','.m4v','.ts','.m2ts',
                 '.wmv','.flv','.webm','.ogv','.divx','.mpg','.mpeg',
                 '.m2v','.vob','.strm'}
AUDIO_EXTS    = {'.mp3','.flac','.aac','.ogg','.wav','.wma','.m4a','.opus'}
SKIP_EXTS     = {'.nfo','.jpg','.jpeg','.png','.gif','.tbn','.xml',
                 '.srt','.ass','.ssa','.sub','.idx','.vtt'}

# Patterns stripped from folder names to produce clean show titles
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
    re.IGNORECASE
)
_SEASON_TAG   = re.compile(r'\bS\d{1,2}\b', re.IGNORECASE)
_YEAR_RANGE   = re.compile(r'\b\d{4}-\d{4}\b')          # e.g. 2024-2025
_YEAR         = re.compile(r'\b(19|20)\d{2}\b')
_GROUPS       = re.compile(r'[-]\s*\w+$')                 # trailing -GroupName
_BRACKETS     = re.compile(r'\[.*?\]|\((?!\d{4}\))[^)]*\)')  # [...] and (...) except (year)
_DOTS_DASHES  = re.compile(r'[._]+')
_MULTI_SPACE  = re.compile(r'\s{2,}')


def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log('[plugin.video.torbox] {}'.format(msg), level)


# ---------------------------------------------------------------------------
# Overrides management  (overrides.json in addon profile)
# ---------------------------------------------------------------------------

def load_overrides():
    """
    Load manual overrides.
    Format:
    {
      "1883 S01 1080p TV+ WEB-DL [TR-EN] AAC2.0 H264-TURG": {
        "title": "1883",
        "year": 2021,
        "tvdb_id": "396390"
      },
      "Landman - Season 01 [2024-2025] ...": {
        "title": "Landman",
        "year": 2024,
        "tvdb_id": "XXXXXX"
      }
    }
    Keys are the raw TorBox folder names (without trailing slash).
    """
    if not xbmcvfs.exists(OVERRIDES_FILE):
        return {}
    try:
        with xbmcvfs.File(OVERRIDES_FILE, 'r') as f:
            return json.loads(f.read())
    except Exception as e:
        log('Failed to load overrides: {}'.format(e), xbmc.LOGWARNING)
        return {}


def save_overrides(data):
    if not xbmcvfs.exists(PROFILE_PATH):
        xbmcvfs.mkdirs(PROFILE_PATH)
    try:
        with xbmcvfs.File(OVERRIDES_FILE, 'w') as f:
            f.write(json.dumps(data, indent=2))
    except Exception as e:
        log('Failed to save overrides: {}'.format(e), xbmc.LOGWARNING)


# ---------------------------------------------------------------------------
# Name cleaning
# ---------------------------------------------------------------------------

def clean_show_name(raw_name):
    """
    Strip quality/encoding tags from a TorBox folder name and return
    (clean_title, year_or_None).

    Examples:
      "1883 S01 1080p TV+ WEB-DL [TR-EN] AAC2.0 H264-TURG"  -> ("1883", None)
      "Landman - Season 01 [2024-2025] 1080p BDRip ..."       -> ("Landman", 2024)
      "Twin.Peaks.1990.S01-S03.1080p.BluRay.x265"            -> ("Twin Peaks", 1990)
      "Peaky.Blinders.The.Immortal.Man.2026.1080p.NF.WEBRip" -> ("Peaky Blinders The Immortal Man", 2026)
    """
    s = raw_name

    # Replace dots/underscores with spaces first (handle Scene-style names)
    # but only if there are multiple dots (not a real title with one dot)
    if s.count('.') >= 2:
        s = _DOTS_DASHES.sub(' ', s)

    # Extract year before we destroy it
    year = None
    yr_range = _YEAR_RANGE.search(s)
    if yr_range:
        year = int(yr_range.group().split('-')[0])
        s = s.replace(yr_range.group(), '')
    else:
        yr = _YEAR.search(s)
        if yr:
            year = int(yr.group())

    # Remove bracketed content (except (year))
    s = _BRACKETS.sub(' ', s)

    # Remove season tags like S01, S01-S03
    s = re.sub(r'\bS\d{1,2}(?:-S\d{1,2})?\b', ' ', s, flags=re.IGNORECASE)
    # Remove "Season XX" or "Season XX-XX"
    s = re.sub(r'\bSeason\s+\d{1,2}(?:\s*-\s*\d{1,2})?\b', ' ', s, flags=re.IGNORECASE)

    # Remove quality tags
    s = _QUALITY_TAGS.sub(' ', s)

    # Remove year now that we've captured it
    s = _YEAR.sub(' ', s)

    # Remove trailing group name after dash
    s = re.sub(r'\s+-\s*\w+$', '', s)
    s = re.sub(r'-\w+$', '', s)

    # Strip leftover punctuation
    s = re.sub(r'[+]', ' ', s)
    s = re.sub(r'[^\w\s\'\-\.]', ' ', s)

    # Collapse whitespace
    s = _MULTI_SPACE.sub(' ', s).strip(' -.')

    return s, year


# def extract_episode_info(filename):
#     """
#     Extract season/episode numbers from a filename.
#     Returns (season, episode) or (None, None).
#     """
#     # Standard SxxExx
#     m = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', filename)
#     if m:
#         return int(m.group(1)), int(m.group(2))
#     # xXXeXX or 1x01 style
#     m = re.search(r'(\d{1,2})[xX](\d{2,3})', filename)
#     if m:
#         return int(m.group(1)), int(m.group(2))
#     return None, None

def extract_episode_info(filename):
    patterns = [
        r'[Ss](\d{1,2})[.\-_ ]?[Ee](\d{1,3})',
        r'(\d{1,2})[xX](\d{2,3})',
    ]

    for pattern in patterns:
        m = re.search(pattern, filename)
        if m:
            return int(m.group(1)), int(m.group(2))

    return None, None


# ---------------------------------------------------------------------------
# Account helpers
# ---------------------------------------------------------------------------

def get_accounts():
    accounts = []
    for i in range(1, 4):
        if not ADDON.getSettingBool('account{}_enabled'.format(i)):
            continue
        name     = ADDON.getSettingString('account{}_name'.format(i))
        url      = ADDON.getSettingString('account{}_url'.format(i)).rstrip('/')
        username = ADDON.getSettingString('account{}_username'.format(i))
        password = ADDON.getSettingString('account{}_password'.format(i))
        if url and username and password:
            accounts.append({
                'index': i,
                'name': name or 'Account {}'.format(i),
                'url': url,
                'username': username,
                'password': password,
            })
    return accounts


def get_account(index):
    return next((a for a in get_accounts() if a['index'] == index), None)


def make_auth_header(username, password):
    creds   = '{}:{}'.format(username, password)
    encoded = base64.b64encode(creds.encode('utf-8')).decode('utf-8')
    return 'Basic {}'.format(encoded)


# ---------------------------------------------------------------------------
# WebDAV
# ---------------------------------------------------------------------------

def encode_webdav_url(url):
    """Percent-encode spaces and special chars in URL path without double-encoding."""
    parsed = urlparse(url)
    safe = '/:@!$&\'()*+,;=-._~%'
    from urllib.parse import urlunparse
    encoded_path = quote(unquote(parsed.path), safe=safe)
    return urlunparse((parsed.scheme, parsed.netloc, encoded_path,
                       parsed.params, parsed.query, parsed.fragment))


def propfind(url, username, password, depth=1):
    body = b'''<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
  <prop>
    <resourcetype/>
    <getcontentlength/>
    <getlastmodified/>
    <displayname/>
    <getcontenttype/>
  </prop>
</propfind>'''
    safe_url = encode_webdav_url(url)
    log('PROPFIND: {}'.format(safe_url))
    headers = {
        'Authorization': make_auth_header(username, password),
        'Depth':         str(depth),
        'Content-Type':  'application/xml; charset=utf-8',
        'User-Agent':    'Kodi/TorBox-Plugin',
    }
    req = Request(safe_url, data=body, headers=headers, method='PROPFIND')
    try:
        response = urlopen(req, timeout=30)
        return ET.fromstring(response.read())
    except HTTPError as e:
        log('PROPFIND HTTP {}: {}'.format(e.code, url), xbmc.LOGERROR)
        xbmcgui.Dialog().notification('TorBox', 'HTTP Error {}'.format(e.code), xbmcgui.NOTIFICATION_ERROR)
    except URLError as e:
        log('PROPFIND URLError {}: {}'.format(e.reason, url), xbmc.LOGERROR)
        xbmcgui.Dialog().notification('TorBox', 'Connection failed', xbmcgui.NOTIFICATION_ERROR)
    except ET.ParseError as e:
        log('PROPFIND XML parse error: {}'.format(e), xbmc.LOGERROR)
    return None


def parse_propfind(xml_root, base_url, current_path):
    ns      = {'d': 'DAV:'}
    items   = []
    decoded_current = unquote(current_path).rstrip('/')

    for resp in xml_root.findall('.//d:response', ns):
        href_el = resp.find('d:href', ns)
        if href_el is None:
            continue
        href = href_el.text.strip()
        path = urlparse(href).path

        # Skip the directory itself
        if unquote(path).rstrip('/') == decoded_current:
            continue

        resourcetype  = resp.find('.//d:resourcetype', ns)
        is_collection = (resourcetype is not None and
                         resourcetype.find('d:collection', ns) is not None)

        displayname_el = resp.find('.//d:displayname', ns)
        displayname    = (displayname_el.text
                          if displayname_el is not None and displayname_el.text
                          else None)

        size_el = resp.find('.//d:getcontentlength', ns)
        size    = int(size_el.text) if size_el is not None and size_el.text else 0

        name = displayname or unquote(path.rstrip('/').split('/')[-1])
        if not name:
            continue

        parsed_base = urlparse(base_url)
        full_url    = '{}://{}{}'.format(parsed_base.scheme, parsed_base.netloc, path)

        items.append({
            'name':          name,
            'full_url':      full_url,
            'path':          path,
            'is_collection': is_collection,
            'size':          size,
        })

    return items


# ---------------------------------------------------------------------------
# Plugin URL helpers
# ---------------------------------------------------------------------------

def build_url(params):
    return '{}?{}'.format(BASE_URL, urlencode(params))


def get_params():
    params = {}
    query  = sys.argv[2].lstrip('?')
    if query:
        from urllib.parse import unquote_plus
        for part in query.split('&'):
            if '=' in part:
                k, v       = part.split('=', 1)
                params[k]  = unquote_plus(v)
    return params


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def list_accounts():
    accounts = get_accounts()
    if not accounts:
        xbmcgui.Dialog().ok(
            'TorBox WebDAV',
            'No accounts configured.\n\nOpen Settings and enter your TorBox credentials.'
        )
        ADDON.openSettings()
        return

    for acc in accounts:
        # --- Browse entry (file browser) ---
        li = xbmcgui.ListItem(label='[B]{} — Browse[/B]'.format(acc['name']))
        li.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
        li.setInfo('video', {'title': acc['name'], 'plot': 'Browse files directly'})
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({'action': 'browse', 'account': acc['index'], 'path': '/'}),
            li, isFolder=True
        )

        # --- Library entry (use this URL as your Kodi video source) ---
        lib_url = build_url({'action': 'library_browse', 'account': acc['index'], 'path': '/'})
        li2 = xbmcgui.ListItem(label='{} — Library Source'.format(acc['name']))
        li2.setArt({'icon': 'DefaultAddonVideo.png', 'thumb': 'DefaultAddonVideo.png'})
        li2.setInfo('video', {
            'title': acc['name'],
            'plot': (
                'Add this to your Kodi library:\n\n'
                '1. Settings → Media → Library → Add video source\n'
                '2. Browse → Plugin → TorBox WebDAV\n'
                '3. Choose "{} — Library Source"\n'
                '4. Set content = TV Shows, scraper = TheTVDB\n'
                '5. Scan library'.format(acc['name'])
            )
        })
        xbmcplugin.addDirectoryItem(HANDLE, lib_url, li2, isFolder=True)

        li = xbmcgui.ListItem(
            label='{} — Export Library'.format(acc['name'])
        )

        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({
                'action': 'export_library',
                'account': acc['index']
            }),
            li,
            isFolder=False
        )

    # Overrides manager
    li = xbmcgui.ListItem(label='[COLOR yellow]✎ Manage show overrides[/COLOR]')
    xbmcplugin.addDirectoryItem(HANDLE, build_url({'action': 'view_overrides'}), li, isFolder=False)

    # Settings shortcut
    li = xbmcgui.ListItem(label='[COLOR gray]⚙ Settings[/COLOR]')
    xbmcplugin.addDirectoryItem(HANDLE, build_url({'action': 'settings'}), li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


def list_directory(account_index, remote_path, is_library_root=False):
    """
    Browse a WebDAV path.
    When is_library_root=True the top-level folders are treated as TV shows
    and Kodi library metadata hints are injected.
    """
    account = get_account(account_index)
    if not account:
        xbmcgui.Dialog().notification('TorBox', 'Account not found', xbmcgui.NOTIFICATION_ERROR)
        return

    full_url  = account['url'] + remote_path
    xml_root  = propfind(full_url, account['username'], account['password'], depth=1)
    if xml_root is None:
        return

    items       = parse_propfind(xml_root, account['url'], remote_path)
    overrides   = load_overrides()
    show_hidden = ADDON.getSettingBool('show_hidden')

    # Signal to Kodi what kind of content this is
    if is_library_root:
        xbmcplugin.setContent(HANDLE, 'tvshows')
    else:
        # Detect content type from path depth / files present
        has_video = any(
            os.path.splitext(i['name'])[1].lower() in VIDEO_EXTS
            for i in items if not i['is_collection']
        )
        xbmcplugin.setContent(HANDLE, 'episodes' if has_video else 'tvshows')

    for item in sorted(items, key=lambda x: (not x['is_collection'], x['name'].lower())):
        name = item['name']

        if not show_hidden and name.startswith('.'):
            continue

        ext = os.path.splitext(name)[1].lower()

        # ── FOLDER (show root or season folder) ──────────────────────────
        if item['is_collection']:
            child_path = unquote(item['path'])
            if not child_path.endswith('/'):
                child_path += '/'

            # Always resolve clean title and year (shown in UI + passed to scraper)
            override    = overrides.get(name, {})
            if override:
                clean_title = override.get('title', name)
                year        = override.get('year')
                tvdb_id     = override.get('tvdb_id', '')
                tmdb_id     = override.get('tmdb_id', '')
            else:
                clean_title, year = clean_show_name(name)
                tvdb_id  = ''
                tmdb_id  = ''

            log('Folder: "{}" -> "{}" ({})'.format(name, clean_title, year))

            # Display clean name; show raw name as subtitle so user can tell what it is
            display_label = clean_title
            if year:
                display_label = '{} ({})'.format(clean_title, year)

            li   = xbmcgui.ListItem(label=display_label)
            info = {
                'title':       clean_title,
                'tvshowtitle': clean_title,
                'mediatype':   'tvshow',
            }
            if year:
                info['year'] = year

            # Unique IDs help Kodi scraper find exact match
            try:
                li.setUniqueIDs({
                    'tvdb': tvdb_id,
                    'tmdb': tmdb_id,
                }, defaultUniqueID='tvdb' if tvdb_id else 'tmdb')
            except Exception:
                pass

            # Context menu always available
            li.addContextMenuItems([
                ('Set show title/override',
                 'RunPlugin({})'.format(
                     build_url({'action': 'set_override',
                                'folder_name': name,
                                'account': account_index})
                 )),
                ('Refresh library',
                 'RunPlugin({})'.format(
                     build_url({'action': 'refresh',
                                'folder_name': name})
                 )),
            ])

            li.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
            li.setInfo('video', info)

            xbmcplugin.addDirectoryItem(
                HANDLE,
                build_url({'action': 'browse',
                           'account': account_index,
                           'path': child_path,
                           'library': '1' if is_library_root else '0'}),
                li, isFolder=True
            )

        # ── VIDEO FILE ───────────────────────────────────────────────────
        elif ext in VIDEO_EXTS:
            season, episode = extract_episode_info(name)

            li = xbmcgui.ListItem(label=name)
            info = {
                'title':     name,
                'mediatype': 'episode',
            }
            if season is not None:
                info['season']  = season
                info['episode'] = episode

            li.setInfo('video', info)
            li.setArt({'icon': 'DefaultVideo.png', 'thumb': 'DefaultVideo.png'})
            li.setProperty('IsPlayable', 'true')

            # Mime type
            mimetypes = {
                '.mkv': 'video/x-matroska', '.mp4': 'video/mp4',
                '.avi': 'video/x-msvideo',  '.ts':  'video/mp2t',
                '.mov': 'video/quicktime',   '.webm':'video/webm',
            }
            if ext in mimetypes:
                li.setMimeType(mimetypes[ext])
                li.setContentLookup(False)

            xbmcplugin.addDirectoryItem(
                HANDLE,
                build_url({'action': 'play',
                           'account': account_index,
                           'url': item['full_url']}),
                li, isFolder=False
            )

        elif ext in SKIP_EXTS:
            continue

        else:
            li = xbmcgui.ListItem(label='[COLOR gray]{}[/COLOR]'.format(name))
            li.setInfo('video', {'title': name})
            xbmcplugin.addDirectoryItem(HANDLE, item['full_url'], li, isFolder=False)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def build_authed_url(stream_url, username, password):
    """
    Embed credentials into the URL as https://user:pass@host/path.
    Kodi's internal libcurl handles this natively on all platforms
    including iOS, unlike setHttpHeader which is unreliable.
    Special characters in username/password are percent-encoded.
    """
    parsed = urlparse(stream_url)
    user   = quote(username, safe='')
    pw     = quote(password, safe='')
    from urllib.parse import urlunparse
    netloc_with_auth = '{}:{}@{}'.format(user, pw, parsed.hostname)
    if parsed.port:
        netloc_with_auth += ':{}'.format(parsed.port)
    return urlunparse((parsed.scheme, netloc_with_auth, parsed.path,
                       parsed.params, parsed.query, parsed.fragment))


def play_item(account_index, stream_url):
    """Resolve playback with credentials embedded in URL for universal Kodi compat."""
    account = get_account(account_index)
    if not account:
        xbmcgui.Dialog().notification('TorBox', 'Account not found', xbmcgui.NOTIFICATION_ERROR)
        return

    authed_url = build_authed_url(stream_url, account['username'], account['password'])
    log('Playing (credentials embedded in URL)')

    li = xbmcgui.ListItem(path=authed_url)

    ext = os.path.splitext(stream_url)[1].lower()
    mimetypes = {
        '.mkv': 'video/x-matroska', '.mp4': 'video/mp4',
        '.avi': 'video/x-msvideo',  '.ts':  'video/mp2t',
        '.mov': 'video/quicktime',   '.webm':'video/webm',
    }
    if ext in mimetypes:
        li.setMimeType(mimetypes[ext])
        li.setContentLookup(False)

    xbmcplugin.setResolvedUrl(HANDLE, True, li)


# ---------------------------------------------------------------------------
# Override editor  (context menu action)
# ---------------------------------------------------------------------------

def set_override(folder_name, account_index):
    """
    Interactive dialog to set a manual title/year/TVDB override for a folder.
    """
    overrides   = load_overrides()
    existing    = overrides.get(folder_name, {})
    clean_guess, year_guess = clean_show_name(folder_name)

    kb = xbmcgui.Dialog()

    title = kb.input('Show title for:\n"{}"'.format(folder_name[:60]),
                     defaultt=existing.get('title', clean_guess))
    if title is None:
        return

    year_str = kb.input('Year (leave blank if unknown)',
                        defaultt=str(existing.get('year', year_guess or '')),
                        type=xbmcgui.INPUT_NUMERIC)

    tvdb_id = kb.input('TheTVDB ID (find at thetvdb.com — leave blank to auto)',
                       defaultt=existing.get('tvdb_id', ''))

    entry = {'title': title.strip()}
    if year_str:
        try:
            entry['year'] = int(year_str)
        except ValueError:
            pass
    if tvdb_id.strip():
        entry['tvdb_id'] = tvdb_id.strip()

    overrides[folder_name] = entry
    save_overrides(overrides)

    xbmcgui.Dialog().notification(
        'TorBox', 'Override saved for "{}"'.format(title), xbmcgui.NOTIFICATION_INFO, 3000
    )
    log('Override saved: {} -> {}'.format(folder_name, entry))


def view_overrides():
    """Show all current overrides and allow deletion."""
    overrides = load_overrides()
    if not overrides:
        xbmcgui.Dialog().ok('TorBox Overrides', 'No overrides configured yet.\n\nLong-press a show in the library view and choose "Set show override".')
        return

    items = list(overrides.items())
    labels = ['{} → {} ({})'.format(
        k[:40], v.get('title', '?'), v.get('year', '?')
    ) for k, v in items]

    idx = xbmcgui.Dialog().select('TorBox Overrides — select to delete', labels)
    if idx < 0:
        return

    folder_name, entry = items[idx]
    if xbmcgui.Dialog().yesno('Delete override?',
                               'Remove override for "{}"?'.format(entry.get('title', folder_name))):
        del overrides[folder_name]
        save_overrides(overrides)
        xbmcgui.Dialog().notification('TorBox', 'Override removed', xbmcgui.NOTIFICATION_INFO, 2000)


# ---------------------------------------------------------------------------
# Library source entry points
# ---------------------------------------------------------------------------

def ensure_video_source(name, path):
    sources_file = xbmcvfs.translatePath(
        "special://profile/sources.xml"
    )

    if not os.path.exists(sources_file):
        root = ET.Element("sources")
        ET.SubElement(root, "video")
        ET.ElementTree(root).write(
            sources_file,
            encoding="utf-8",
            xml_declaration=True
        )

    tree = ET.parse(sources_file)
    root = tree.getroot()

    video = root.find("video")
    if video is None:
        video = ET.SubElement(root, "video")

    for source in video.findall("source"):
        src_name = source.find("name")
        if src_name is not None and src_name.text == name:
            return

    source = ET.SubElement(video, "source")

    ET.SubElement(source, "name").text = name

    p = ET.SubElement(source, "path")
    p.set("pathversion", "1")
    p.text = path

    ET.SubElement(source, "allowsharing").text = "true"

    tree.write(
        sources_file,
        encoding="utf-8",
        xml_declaration=True
    )

def list_library_accounts():
    """
    Root for when the addon is used as a Kodi library source.
    Each account appears as a TV show root.
    """
    accounts = get_accounts()
    if not accounts:
        xbmcgui.Dialog().ok('TorBox', 'Configure accounts in Settings first.')
        ADDON.openSettings()
        return

    xbmcplugin.setContent(HANDLE, 'tvshows')

    for acc in accounts:
        li = xbmcgui.ListItem(label=acc['name'])
        li.setArt({'icon': 'DefaultFolder.png'})
        li.setInfo('video', {'title': acc['name'], 'mediatype': 'tvshow'})
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({'action': 'library_browse',
                       'account': acc['index'],
                       'path': '/'}),
            li, isFolder=True
        )

    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def get_library_path():
    path = ADDON.getSettingString('library_path')

    if not path:
        xbmcgui.Dialog().notification(
            'TorBox',
            'Library path not configured',
            xbmcgui.NOTIFICATION_ERROR
        )
        return None

    return xbmcvfs.translatePath(path)


def write_text_file(path, content):
    folder = os.path.dirname(path)

    if not xbmcvfs.exists(folder):
        xbmcvfs.mkdirs(folder)

    with xbmcvfs.File(path, 'w') as f:
        f.write(content)


def write_tvshow_nfo(show_folder, title, tvdb_id=None):
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tvshow>',
        '  <title>{}</title>'.format(title)
    ]

    if tvdb_id:
        xml.append(
            '  <uniqueid type="tvdb" default="true">{}</uniqueid>'.format(
                tvdb_id
            )
        )

        xml.append('</tvshow>')

        write_text_file(
            os.path.join(show_folder, 'tvshow.nfo'),
            '\n'.join(xml)
        )


def walk_webdav(account, remote_path):
    """
    Recursively returns all video files beneath remote_path.
    """

    full_url = account['url'] + remote_path

    xml_root = propfind(
        full_url,
        account['username'],
        account['password'],
        depth=1
    )

    if xml_root is None:
        return []

    items = parse_propfind(
        xml_root,
        account['url'],
        remote_path
    )

    files = []

    for item in items:

        if item['is_collection']:

            child = unquote(item['path'])

            if not child.endswith('/'):
                child += '/'

            files.extend(
                walk_webdav(account, child)
            )

        else:
            ext = os.path.splitext(item['name'])[1].lower()

            if ext in VIDEO_EXTS:
                files.append(item)

    return files

def export_library(account_index):
    account = get_account(account_index)

    if not account:
        xbmcgui.Dialog().notification(
            'TorBox',
            'Account not found',
            xbmcgui.NOTIFICATION_ERROR
        )
        return

    library_root = get_library_path()

    if not library_root:
        return

    if not xbmcvfs.exists(library_root):
        xbmcvfs.mkdirs(library_root)

    overrides = load_overrides()

    root_xml = propfind(
        account['url'] + '/',
        account['username'],
        account['password'],
        depth=1
    )

    if root_xml is None:
        return

    shows = parse_propfind(
        root_xml,
        account['url'],
        '/'
    )

    created = 0

    for show in shows:

        if not show['is_collection']:
            continue

        raw_name = show['name']

        override = overrides.get(raw_name, {})

        if override:
            clean_title = override.get('title', raw_name)
            tvdb_id = override.get('tvdb_id')
        else:
            clean_title, _ = clean_show_name(raw_name)
            tvdb_id = None

        show_folder = os.path.join(
            library_root,
            clean_title
        )

        if not xbmcvfs.exists(show_folder):
            xbmcvfs.mkdirs(show_folder)

        write_tvshow_nfo(
            show_folder,
            clean_title,
            tvdb_id
        )

        child_path = unquote(show['path'])

        if not child_path.endswith('/'):
            child_path += '/'

        episodes = walk_webdav(
            account,
            child_path
        )

        for ep in episodes:

            season, episode = extract_episode_info(
                ep['name']
            )

            if season is None:
                continue

            # season_folder = os.path.join(
            #     show_folder,
            #     'Season {:02d}'.format(season)
            # )

            # if not xbmcvfs.exists(season_folder):
            #     xbmcvfs.mkdirs(season_folder)

            plugin_url = build_url({
                'action': 'play',
                'account': account_index,
                'url': ep['full_url']
            })

            strm_name = '{}.S{:02d}E{:02d}.strm'.format(
                clean_title,
                season,
                episode
            )

            strm_path = os.path.join(
                # season_folder,
                show_folder,
                strm_name
            )

            write_text_file(
                strm_path,
                plugin_url
            )

            created += 1

    xbmcgui.Dialog().ok(
        'TorBox',
        'Export complete\n\n{} STRM files generated'.format(
            created
        )
    )

    if not ADDON.getSettingBool('library_source_created'):
        ensure_video_source(
            'TorBox Library',
            library_root
        )

        ADDON.setSettingBool(
            'library_source_created',
            True
        )

        xbmcgui.Dialog().ok(
            'TorBox',
            'TorBox Library source has been added.\n\n'
            'Go to Videos → Files → TorBox Library\n'
            'and set Content = TV Shows.'
        )

        xbmc.executebuiltin('ActivateWindow(Videos,Files,return)')

    else:
        xbmc.executebuiltin('UpdateLibrary(video)')

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def router():
    params  = get_params()
    action  = params.get('action', 'root')
    log('Action={} Params={}'.format(action, params))

    if action == 'root':
        list_accounts()

    elif action == 'browse':
        account_index   = int(params.get('account', 1))
        path            = params.get('path', '/')
        is_lib          = params.get('library', '0') == '1'
        list_directory(account_index, path, is_library_root=is_lib)

    elif action == 'library_browse':
        account_index = int(params.get('account', 1))
        path          = params.get('path', '/')
        # Top level = show roots; deeper = episodes
        is_root       = (path == '/')
        list_directory(account_index, path, is_library_root=is_root)

    elif action == 'play':
        account_index = int(params.get('account', 1))
        play_item(account_index, params.get('url', ''))

    elif action == 'set_override':
        set_override(params.get('folder_name', ''), int(params.get('account', 1)))

    elif action == 'view_overrides':
        view_overrides()

    elif action == 'settings':
        ADDON.openSettings()

    elif action == 'refresh':
        xbmc.executebuiltin('UpdateLibrary(video)')
    
    elif action == 'export_library':
        export_library(
            int(params.get('account', 1))
        )

    else:
        log('Unknown action: {}'.format(action), xbmc.LOGWARNING)
        list_accounts()


if __name__ == '__main__':
    router()
