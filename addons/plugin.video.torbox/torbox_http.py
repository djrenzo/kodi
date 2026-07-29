from json import loads
import os
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import xbmcvfs

from torbox_common import log

HEADERS = {'User-Agent': 'Kodi/TorBox-Plugin'}
TIMEOUT = 30
TIMEOUT_JSON = 15


def _normalize_url(url):
    """Return a safely encoded URL path/query for urllib requests."""
    parsed = urlsplit(url)

    encoded_path = quote(parsed.path or '', safe='/%:@!$&\'()*+,;=-._~')

    # parse_qsl/urlencode normalizes percent-encoding and handles unicode safely.
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    encoded_query = urlencode(query_pairs, doseq=True)

    return urlunsplit((parsed.scheme, parsed.netloc, encoded_path, encoded_query, parsed.fragment))


def _normalize_data(data, headers):
    if data is None or isinstance(data, bytes):
        return data

    if isinstance(data, str):
        return data.encode('utf-8')

    if isinstance(data, dict):
        if 'Content-Type' not in headers and 'content-type' not in headers:
            headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=utf-8'
        return urlencode(data, doseq=True).encode('utf-8')

    return str(data).encode('utf-8')

def http_req(url, method='GET', data=None, headers=None, timeout=TIMEOUT):
    """Make an HTTP request and return the response data."""
    request_headers = dict(HEADERS)
    if headers:
        request_headers.update(headers)

    try:
        normalized_url = _normalize_url(url)
        normalized_data = _normalize_data(data, request_headers)
        req = Request(normalized_url, data=normalized_data, headers=request_headers, method=method)
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


