import json
import os
import time

import xbmcvfs

from torbox_http import fetch_json
from torbox_common import PROFILE_PATH, log

BASE_URL = "https://raw.githubusercontent.com/djrenzo/metadata/main/{media_type}/{service}/{id}.json"
CACHE_FILE = os.path.join(PROFILE_PATH, 'datafetcher_cache.json')
CACHE_TTL_SECONDS = 12 * 60 * 60

class DataFetcher():

    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.cached_by_tmdb = {}
        self.cached_by_imdb = {}
        self._disk_cache = self._load_disk_cache()

    def _now(self):
        return int(time.time())

    def _series_to_payload(self, series):
        return {
            'imdb_data': series.imdb_data,
            'tmdb_data': series.tmdb_data,
            'imdb_id': series.imdb_id,
            'tmdb_id': series.tmdb_id,
            'ts': self._now(),
        }

    def _payload_to_series(self, payload):
        if not isinstance(payload, dict):
            return None

        series = Series()
        series.imdb_data = payload.get('imdb_data')
        series.tmdb_data = payload.get('tmdb_data')

        imdb_id = payload.get('imdb_id')
        tmdb_id = payload.get('tmdb_id')

        series.imdb_id = str(imdb_id).strip() if imdb_id else None
        series.tmdb_id = str(tmdb_id).strip() if tmdb_id else None
        return series

    def _cache_key(self, tmdb_id=None, imdb_id=None):
        if tmdb_id:
            return 'tmdb:{}'.format(str(tmdb_id).strip())
        if imdb_id:
            return 'imdb:{}'.format(str(imdb_id).strip())
        return None

    def _is_fresh(self, payload):
        ts = payload.get('ts', 0) if isinstance(payload, dict) else 0
        return (self._now() - int(ts or 0)) <= CACHE_TTL_SECONDS

    def _load_disk_cache(self):
        if not xbmcvfs.exists(CACHE_FILE):
            return {}

        try:
            with xbmcvfs.File(CACHE_FILE, 'r') as fh:
                raw = fh.read()
        except Exception as exc:
            log('DataFetcher cache read error: {}'.format(exc))
            return {}

        if not raw:
            return {}

        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return {}
        except Exception as exc:
            log('DataFetcher cache parse error: {}'.format(exc))
            return {}

        filtered = {}
        for key, payload in parsed.items():
            if not isinstance(payload, dict):
                continue
            if self._is_fresh(payload):
                filtered[key] = payload

        if len(filtered) != len(parsed):
            self._disk_cache = filtered
            self._save_disk_cache()

        return filtered

    def _save_disk_cache(self):
        try:
            folder = os.path.dirname(CACHE_FILE)
            if folder and not xbmcvfs.exists(folder):
                xbmcvfs.mkdirs(folder)

            with xbmcvfs.File(CACHE_FILE, 'w') as fh:
                fh.write(json.dumps(self._disk_cache))
        except Exception as exc:
            log('DataFetcher cache write error: {}'.format(exc))

    def _cache_series(self, series):
        if not series:
            return

        if series.tmdb_id:
            self.cached_by_tmdb[series.tmdb_id] = series
        if series.imdb_id:
            self.cached_by_imdb[series.imdb_id] = series

        payload = self._series_to_payload(series)
        tmdb_key = self._cache_key(tmdb_id=series.tmdb_id)
        imdb_key = self._cache_key(imdb_id=series.imdb_id)

        if tmdb_key:
            self._disk_cache[tmdb_key] = payload
        if imdb_key:
            self._disk_cache[imdb_key] = payload

        self._save_disk_cache()

    def _get_cached_series(self, tmdb_id=None, imdb_id=None):
        tmdb_id = str(tmdb_id).strip() if tmdb_id else None
        imdb_id = str(imdb_id).strip() if imdb_id else None

        if tmdb_id and tmdb_id in self.cached_by_tmdb:
            return self.cached_by_tmdb[tmdb_id]
        if imdb_id and imdb_id in self.cached_by_imdb:
            return self.cached_by_imdb[imdb_id]

        key = self._cache_key(tmdb_id=tmdb_id, imdb_id=imdb_id)
        payload = self._disk_cache.get(key) if key else None

        if payload and self._is_fresh(payload):
            series = self._payload_to_series(payload)
            self._cache_series(series)
            return series

        # Fallback scan lets imdb-only/tmdb-only lookups reuse older key variants.
        for cached_payload in self._disk_cache.values():
            if not self._is_fresh(cached_payload):
                continue
            if tmdb_id and str(cached_payload.get('tmdb_id') or '').strip() == tmdb_id:
                series = self._payload_to_series(cached_payload)
                self._cache_series(series)
                return series
            if imdb_id and str(cached_payload.get('imdb_id') or '').strip() == imdb_id:
                series = self._payload_to_series(cached_payload)
                self._cache_series(series)
                return series

        return None

    def _fetch_data(self, media_type, service, id):
        """Fetch data for the given media type, service, and ID."""
        url = self.base_url.format(media_type=media_type, service=service, id=id)
        return fetch_json(url)

    def fetch_series(self, tmdb_id=None, imdb_id=None):
        """Fetch series data for the given service and ID."""
        if not imdb_id and not tmdb_id:
            return None

        if tmdb_id:
            tmdb_id = str(tmdb_id).strip()
            cached = self._get_cached_series(tmdb_id=tmdb_id)
            if cached:
                return cached

            series = Series()
            service = 'tmdb'
            id = tmdb_id
            data = self._fetch_data('tv', service, id)
            if not isinstance(data, dict):
                return None
            series.add_data(id, data, service)

            imdb_id = data.get("external_ids", {}).get('imdb_id')
            if imdb_id:
                imdb_data = self._fetch_data('tv', 'imdb', imdb_id)
                if isinstance(imdb_data, dict):
                    series.add_data(imdb_id, imdb_data, 'imdb')

            self._cache_series(series)

        elif imdb_id:
            imdb_id = str(imdb_id).strip()
            cached = self._get_cached_series(imdb_id=imdb_id)
            if cached:
                return cached

            series = Series()
            service = 'imdb'
            id = imdb_id
            data = self._fetch_data('tv', service, id)
            if not isinstance(data, dict):
                return None
            series.add_data(id, data, service)

            tmdb_id = data.get('moviedb_id')
            if tmdb_id:
                tmdb_id = str(tmdb_id).strip()
                tmdb_data = self._fetch_data('tv', 'tmdb', tmdb_id)
                if isinstance(tmdb_data, dict):
                    series.add_data(tmdb_id, tmdb_data, 'tmdb')

            self._cache_series(series)

        else:
            return None
        return series

class Series():
    def __init__(self):
        self.imdb_data = None
        self.tmdb_data = None
        self.imdb_id = None
        self.tmdb_id = None

    def add_data(self, id, data, service):
        if service == 'imdb':
            self.imdb_data = data
            self.imdb_id = str(id).strip()
        elif service == 'tmdb':
            self.tmdb_data = data
            self.tmdb_id = str(id).strip()