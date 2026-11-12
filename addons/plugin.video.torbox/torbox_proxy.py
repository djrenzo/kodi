"""Local streaming proxy that keeps TorBox playback alive when a download server drops.

Kodi plays http://127.0.0.1:<port>/stream/<filename>?a=<account>&u=<upstream url>.
The proxy requests the upstream file with the same Range Kodi asked for and copies
the bytes through. When the upstream connection dies or stalls mid-stream, it asks
the original URL again (TorBox hands out a fresh download server) with a Range that
starts at the first byte Kodi hasn't received yet, and carries on in the same
response. Every reconnect is appended to a small JSON-lines log that the
Management menu can show.

Runs inside the addon's service process, so it must not import torbox_common
(that module reads sys.argv, which only exists for plugin invocations).
"""

import base64
import json
import os
import re
import socket
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = 'plugin.video.torbox'
PORT_PROPERTY = 'torbox.proxy.port'
PREFERRED_PORT = 52741

PROFILE_DIR = xbmcvfs.translatePath('special://profile/addon_data/{}/'.format(ADDON_ID))
RECONNECT_LOG = os.path.join(PROFILE_DIR, 'reconnects.log')
RECONNECT_LOG_MAX_LINES = 500

CHUNK_SIZE = 512 * 1024
# A download server that sends nothing for this long is treated as dead. Kept well
# under Kodi's own 20 s low-speed timeout, so the proxy recovers before Kodi gives up.
UPSTREAM_TIMEOUT = 10
RECONNECT_DELAYS = (0, 1, 2, 4, 8)

PASS_HEADERS = ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges',
                'Last-Modified', 'ETag')
USER_AGENT = 'Kodi/TorBox-Plugin'

_log_lock = threading.Lock()


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[plugin.video.torbox] [proxy] {}'.format(msg), level)


# --- reconnect log -----------------------------------------------------------------

def record_reconnect(entry):
    """Append one reconnect event, keeping only the newest RECONNECT_LOG_MAX_LINES."""
    entry = dict(entry, time=time.strftime('%Y-%m-%d %H:%M:%S'))
    line = json.dumps(entry, ensure_ascii=False)
    with _log_lock:
        try:
            os.makedirs(PROFILE_DIR, exist_ok=True)
            lines = []
            if os.path.exists(RECONNECT_LOG):
                with open(RECONNECT_LOG, 'r', encoding='utf-8') as f:
                    lines = f.read().splitlines()
            lines.append(line)
            lines = lines[-RECONNECT_LOG_MAX_LINES:]
            with open(RECONNECT_LOG, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as exc:
            log('Could not write reconnect log: {}'.format(exc), xbmc.LOGWARNING)


def read_reconnects():
    """Return logged reconnect events, newest first."""
    try:
        with open(RECONNECT_LOG, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
    except (IOError, OSError):
        return []
    entries = []
    for line in reversed(lines):
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries


def clear_reconnects():
    with _log_lock:
        try:
            os.remove(RECONNECT_LOG)
        except OSError:
            pass


# --- upstream requests -------------------------------------------------------------

class _StripAuthOnHostChange(HTTPRedirectHandler):
    """Follow redirects, but don't hand the WebDAV login to a different host (the CDN)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urlparse(newurl).hostname != urlparse(req.full_url).hostname:
            new.headers.pop('Authorization', None)
            new.unredirected_hdrs.pop('Authorization', None)
        return new


_opener = build_opener(_StripAuthOnHostChange, HTTPSHandler(context=ssl.create_default_context()))


def _encode_url(url):
    parsed = urlparse(url)
    path = quote(unquote(parsed.path), safe="/:@!$&'()*+,;=-._~%")
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))


def _auth_header(account_index):
    if not account_index:
        return None
    addon = xbmcaddon.Addon(ADDON_ID)
    user = addon.getSettingString('account{}_username'.format(account_index))
    password = addon.getSettingString('account{}_password'.format(account_index))
    if not user:
        return None
    token = base64.b64encode('{}:{}'.format(user, password).encode('utf-8')).decode('ascii')
    return 'Basic {}'.format(token)


def _open_upstream(url, auth, range_header, method='GET'):
    headers = {'User-Agent': USER_AGENT}
    if auth:
        headers['Authorization'] = auth
    if range_header:
        headers['Range'] = range_header
    req = Request(url, headers=headers, method=method)
    # One socket timeout covers both connecting and every later read.
    return _opener.open(req, timeout=UPSTREAM_TIMEOUT)


_RANGE_RE = re.compile(r'bytes=(\d*)-(\d*)')
_CONTENT_RANGE_RE = re.compile(r'bytes (\d+)-(\d+)/(\d+|\*)')


def _parse_range(value):
    match = _RANGE_RE.match(value or '')
    if not match or not match.group(1):
        return None, None
    end = int(match.group(2)) if match.group(2) else None
    return int(match.group(1)), end


# --- HTTP server -------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):  # keep BaseHTTPRequestHandler quiet
        pass

    def do_HEAD(self):
        self._serve(head=True)

    def do_GET(self):
        self._serve(head=False)

    def _serve(self, head):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        upstream = query.get('u', [''])[0]
        if not parsed.path.startswith('/stream/') or not upstream:
            self.send_error(404)
            return

        url = _encode_url(upstream)
        auth = _auth_header(query.get('a', [''])[0])
        name = unquote(parsed.path.rsplit('/', 1)[-1])
        client_range = self.headers.get('Range')

        try:
            # Always GET upstream: not every download server answers HEAD. For a HEAD
            # from Kodi only the headers are passed on and the body is never read.
            resp = _open_upstream(url, auth, client_range)
        except HTTPError as exc:
            log('Upstream HTTP {} for {}'.format(exc.code, name), xbmc.LOGWARNING)
            self.send_error(exc.code)
            return
        except Exception as exc:
            log('Upstream open failed for {}: {}'.format(name, exc), xbmc.LOGWARNING)
            self.send_error(502)
            return

        with resp:
            self.send_response(resp.status)
            for header in PASS_HEADERS:
                value = resp.headers.get(header)
                if value:
                    self.send_header(header, value)
            self.end_headers()
            if head:
                return

            length = resp.headers.get('Content-Length')
            expected = int(length) if length and length.isdigit() else None
            start, _ = _parse_range(client_range)
            if resp.status == 206:
                match = _CONTENT_RANGE_RE.match(resp.headers.get('Content-Range', ''))
                if match:
                    start = int(match.group(1))
            if start is None:
                start = 0
            self._pump(resp, url, auth, name, start, expected)

    def _pump(self, resp, url, auth, name, start, expected):
        """Copy upstream to Kodi; on upstream failure, resume from the next byte."""
        buf = bytearray(CHUNK_SIZE)
        view = memoryview(buf)
        sent = 0
        end = start + expected - 1 if expected is not None else None
        current = resp

        while True:
            error = None
            try:
                n = current.readinto(buf)
                if n:
                    try:
                        self.wfile.write(view[:n])
                    except (BrokenPipeError, ConnectionResetError, socket.timeout, OSError):
                        return  # Kodi closed the connection (seek/stop): nothing to fix
                    sent += n
                    continue
                if expected is None or sent >= expected:
                    return  # clean end of file
                error = 'connection closed early'
            except (socket.timeout, TimeoutError):
                error = 'stalled for {}s'.format(UPSTREAM_TIMEOUT)
            except Exception as exc:
                error = '{}: {}'.format(type(exc).__name__, exc)

            if current is not resp:
                current.close()
            current = self._reconnect(url, auth, name, start + sent, end, error)
            if current is None:
                return

    def _reconnect(self, url, auth, name, offset, end, error):
        range_header = 'bytes={}-{}'.format(offset, end if end is not None else '')
        started = time.time()
        log('Stream dropped at byte {} of {} ({}), reconnecting'.format(offset, name, error),
            xbmc.LOGWARNING)

        last_error = error
        for attempt, delay in enumerate(RECONNECT_DELAYS, 1):
            if delay and xbmc.Monitor().waitForAbort(delay):
                return None
            try:
                resp = _open_upstream(url, auth, range_header)
                match = _CONTENT_RANGE_RE.match(resp.headers.get('Content-Range', ''))
                if resp.status != 206 or not match or int(match.group(1)) != offset:
                    resp.close()
                    raise IOError('server ignored resume range (HTTP {})'.format(resp.status))
            except Exception as exc:
                last_error = '{}: {}'.format(type(exc).__name__, exc)
                continue

            record_reconnect({
                'file': name, 'offset': offset, 'error': error, 'attempts': attempt,
                'downtime_ms': int((time.time() - started) * 1000), 'result': 'resumed',
            })
            log('Resumed {} at byte {} after {} attempt(s)'.format(name, offset, attempt))
            return resp

        record_reconnect({
            'file': name, 'offset': offset, 'error': error, 'attempts': len(RECONNECT_DELAYS),
            'downtime_ms': int((time.time() - started) * 1000), 'result': 'failed',
            'last_error': last_error,
        })
        log('Giving up on {} at byte {}: {}'.format(name, offset, last_error), xbmc.LOGERROR)
        return None


class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class StreamProxy:
    def __init__(self):
        self._server = None
        self._thread = None

    def start(self):
        for port in (PREFERRED_PORT, 0):
            try:
                self._server = _Server(('127.0.0.1', port), _Handler)
                break
            except OSError as exc:
                log('Port {} unavailable: {}'.format(port, exc), xbmc.LOGWARNING)
        if self._server is None:
            return False
        port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        xbmcgui.Window(10000).setProperty(PORT_PROPERTY, str(port))
        log('Listening on 127.0.0.1:{}'.format(port))
        return True

    def stop(self):
        xbmcgui.Window(10000).clearProperty(PORT_PROPERTY)
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


def proxied_url(stream_url, account_index=None):
    """Wrap a stream URL in the local proxy, or return None when the proxy isn't usable."""
    if not xbmcaddon.Addon(ADDON_ID).getSettingBool('stream_proxy'):
        return None
    port = xbmcgui.Window(10000).getProperty(PORT_PROPERTY)
    if not port:
        return None
    # Keep the real filename last in the path so Kodi still sees the extension.
    name = unquote(urlparse(stream_url).path.rstrip('/').rsplit('/', 1)[-1]) or 'stream'
    params = {'u': stream_url}
    if account_index:
        params['a'] = str(account_index)
    return 'http://127.0.0.1:{}/stream/{}?{}'.format(port, quote(name), urlencode(params))
