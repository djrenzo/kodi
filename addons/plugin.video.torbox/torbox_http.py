from json import loads
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmcvfs

from torbox_common import log

HEADERS = {'User-Agent': 'Kodi/TorBox-Plugin'}
TIMEOUT = 30
TIMEOUT_JSON = 15

def http_req(url, method='GET', data=None, headers=None, timeout=TIMEOUT):
    """Make an HTTP request and return the response data."""
    if headers is None:
        headers = HEADERS

    try:
        req = Request(url, data=data, headers=headers, method=method)
        response = urlopen(req, timeout=timeout)
        return response.read()
    except (HTTPError, URLError) as exc:
        log('http_req error: {}'.format(exc), 'warning')
        return None


def download(url, dest_path):
    try:
        data = http_req(url, method='GET', headers=HEADERS, timeout=TIMEOUT)

        folder = os.path.dirname(dest_path)
        if not xbmcvfs.exists(folder):
            xbmcvfs.mkdirs(folder)

        with xbmcvfs.File(dest_path, 'w') as fh:
            fh.write(data.decode('utf-8', errors='replace'))
        return True
    
    except Exception as exc:
        log('download error: {}'.format(exc), 'warning')
        return False

def fetch_json(url, headers=HEADERS):
    try:
        data = http_req(url, method='GET', headers=headers, timeout=TIMEOUT_JSON)
        return loads(data.decode('utf-8')) if data else None
    
    except Exception as exc:
        raise ValueError('fetch_json error: {}'.format(exc))


