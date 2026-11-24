"""Minimal Supabase client (Auth + PostgREST) on urllib, for pushing the catalog.

Logs in with the email/password of a Supabase user (Authentication > Users) and sends
that user's access token with every request, so the database's row level security
decides what is allowed. The session is cached in the addon profile and refreshed
when it expires.
"""

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import xbmc
import xbmcvfs

from torbox_common import ADDON, PROFILE_PATH, log

SESSION_FILE = os.path.join(PROFILE_PATH, 'supabase_session.json')
TIMEOUT = 60
PAGE_SIZE = 1000   # PostgREST's default max rows per response
BATCH_SIZE = 500   # rows per insert/upsert request


class SupabaseError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def project_url(url):
    """https://<ref>.supabase.co, also when a URL with a path was pasted (the dashboard's
    Data API page shows https://<ref>.supabase.co/rest/v1)."""
    url = (url or '').strip()
    parts = urlsplit(url)
    if parts.scheme and parts.netloc:
        return '{}://{}'.format(parts.scheme, parts.netloc)
    return url.rstrip('/')


def get_config():
    return {
        'url': project_url(ADDON.getSettingString('supabase_url')),
        'key': ADDON.getSettingString('supabase_key').strip(),
        'email': ADDON.getSettingString('supabase_email').strip(),
        'password': ADDON.getSettingString('supabase_password'),
    }


def is_configured():
    config = get_config()
    return all(config.values())


def _error_message(raw, fallback):
    try:
        body = json.loads(raw.decode('utf-8'))
    except Exception:
        return fallback
    if isinstance(body, dict):
        parts = [body.get(k) for k in ('msg', 'message', 'error_description', 'error', 'details', 'hint')]
        parts = [str(p) for p in parts if p]
        if parts:
            return ' - '.join(dict.fromkeys(parts))
    return fallback


def _http(method, url, headers, body=None):
    """(status, response headers, parsed JSON or None). Raises SupabaseError."""
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        headers = dict(headers, **{'Content-Type': 'application/json'})
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read()
            parsed = json.loads(raw.decode('utf-8')) if raw.strip() else None
            return response.status, response.headers, parsed
    except HTTPError as exc:
        raw = exc.read() or b''
        raise SupabaseError(_error_message(raw, 'HTTP {}'.format(exc.code)), exc.code)
    except (URLError, OSError) as exc:
        raise SupabaseError('Cannot reach Supabase: {}'.format(getattr(exc, 'reason', exc)))


class SupabaseClient:
    def __init__(self, config=None):
        self.config = config or get_config()
        if not all(self.config.values()):
            raise SupabaseError('Supabase is not configured')
        self._session = None

    # --- auth ------------------------------------------------------------------------

    def _load_session(self):
        try:
            with xbmcvfs.File(SESSION_FILE, 'r') as fh:
                session = json.loads(fh.read() or '{}')
        except Exception:
            return None
        if session.get('url') != self.config['url'] or session.get('email') != self.config['email']:
            return None
        return session if session.get('access_token') else None

    def _store_session(self, token_response):
        self._session = {
            'url': self.config['url'],
            'email': self.config['email'],
            'access_token': token_response['access_token'],
            'refresh_token': token_response.get('refresh_token', ''),
            # Renew a minute early so a long push doesn't run into the expiry.
            'expires_at': int(time.time()) + int(token_response.get('expires_in', 3600)) - 60,
        }
        try:
            if not xbmcvfs.exists(PROFILE_PATH):
                xbmcvfs.mkdirs(PROFILE_PATH)
            with xbmcvfs.File(SESSION_FILE, 'w') as fh:
                fh.write(json.dumps(self._session))
        except Exception as exc:
            log('Supabase: could not cache session: {}'.format(exc), xbmc.LOGWARNING)

    def _token(self, grant_type, body):
        url = '{}/auth/v1/token?grant_type={}'.format(self.config['url'], grant_type)
        _, _, response = _http('POST', url, {'apikey': self.config['key']}, body)
        if not response or not response.get('access_token'):
            raise SupabaseError('Supabase login returned no access token')
        self._store_session(response)

    def login(self):
        try:
            self._token('password', {'email': self.config['email'], 'password': self.config['password']})
        except SupabaseError as exc:
            if exc.status in (400, 401):
                raise SupabaseError('Supabase login failed: {}'.format(exc), exc.status)
            raise

    def _access_token(self):
        if self._session is None:
            self._session = self._load_session()
        if self._session and self._session['expires_at'] > time.time():
            return self._session['access_token']
        if self._session and self._session.get('refresh_token'):
            try:
                self._token('refresh_token', {'refresh_token': self._session['refresh_token']})
                return self._session['access_token']
            except SupabaseError as exc:
                log('Supabase: session refresh failed ({}), logging in again'.format(exc))
        self.login()
        return self._session['access_token']

    # --- REST ------------------------------------------------------------------------

    def _rest(self, method, path, params=None, body=None, prefer=None, retry_auth=True):
        url = '{}/rest/v1/{}'.format(self.config['url'], path)
        if params:
            url += '?' + urlencode(params)
        headers = {
            'apikey': self.config['key'],
            'Authorization': 'Bearer {}'.format(self._access_token()),
            'Accept': 'application/json',
        }
        if prefer:
            headers['Prefer'] = prefer
        try:
            return _http(method, url, headers, body)
        except SupabaseError as exc:
            if exc.status == 401 and retry_auth:
                self._session = None
                self.login()
                return self._rest(method, path, params, body, prefer, retry_auth=False)
            raise

    def rpc(self, function, args=None):
        _, _, result = self._rest('POST', 'rpc/{}'.format(function), body=args or {})
        return result

    def select_all(self, table, select, order, **filters):
        """Every matching row (paged; order must be a unique column so pages don't overlap).
        Filters are PostgREST operators: col='eq.value'."""
        rows = []
        offset = 0
        while True:
            params = dict(filters, select=select, order='{}.asc'.format(order), limit=PAGE_SIZE, offset=offset)
            _, _, page = self._rest('GET', table, params)
            rows.extend(page or [])
            if not page or len(page) < PAGE_SIZE:
                return rows
            offset += PAGE_SIZE

    def insert(self, table, row, returning='*'):
        _, _, result = self._rest('POST', table, {'select': returning}, [row], prefer='return=representation')
        return result[0]

    def update(self, table, values, **filters):
        self._rest('PATCH', table, filters, values, prefer='return=minimal')

    def upsert(self, table, rows, on_conflict, returning=None):
        """Insert or update rows (matched on the on_conflict columns), in batches.
        PostgREST wants the same keys in every row of a request, so rows are grouped by
        their key set; columns left out of a row keep their stored value on update.
        Rows with the same on_conflict values are collapsed (last one wins): Postgres
        refuses to update one row twice in a single statement."""
        conflict_columns = on_conflict.split(',')
        unique = {}
        for row in rows:
            unique[tuple(row.get(column) for column in conflict_columns)] = row

        groups = {}
        for row in unique.values():
            groups.setdefault(tuple(sorted(row)), []).append(row)

        returned = []
        for group in groups.values():
            for start in range(0, len(group), BATCH_SIZE):
                params = {'on_conflict': on_conflict}
                if returning:
                    params['select'] = returning
                prefer = 'resolution=merge-duplicates,return={}'.format(
                    'representation' if returning else 'minimal')
                _, _, result = self._rest('POST', table, params, group[start:start + BATCH_SIZE], prefer=prefer)
                if returning:
                    returned.extend(result or [])
        return returned

    def ping(self):
        """One cheap authenticated query. Free projects pause after 7 days without
        activity; this counts as activity."""
        return self.rpc('is_member')

    def delete(self, table, **filters):
        """Delete matching rows; returns how many were removed."""
        if not filters:
            raise SupabaseError('Refusing to delete without a filter')
        _, headers, _ = self._rest('DELETE', table, filters, prefer='return=minimal,count=exact')
        content_range = headers.get('Content-Range') or ''
        total = content_range.rsplit('/', 1)[-1]
        return int(total) if total.isdigit() else 0
