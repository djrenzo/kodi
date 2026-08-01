from torbox_http import fetch_json

BASE_URL = "https://raw.githubusercontent.com/djrenzo/metadata/main/{media_type}/{service}/{id}.json"

class DataFetcher():

    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url

    def _fetch_data(self, media_type, service, id):
        """Fetch data for the given media type, service, and ID."""
        url = self.base_url.format(media_type=media_type, service=service, id=id)
        return fetch_json(url)

    def fetch_series(self, imdb_id=None, tmdb_id=None):
        """Fetch series data for the given service and ID."""
        series = Series()
        if not imdb_id and not tmdb_id:
            return None

        if imdb_id:
            service = 'imdb'
            id = imdb_id
            data = self._fetch_data('tv', service, id)
            series.add_data(id, data, service)

            tmdb_id = data.get('moviedb_id')
            if tmdb_id:
                tmdb_data = self._fetch_data('tv', 'tmdb', tmdb_id)
                series.add_data(tmdb_id, tmdb_data, 'tmdb')

        elif tmdb_id:
            service = 'tmdb'
            id = tmdb_id
            data = self._fetch_data('tv', service, id)
            series.add_data(id, data, service)

            imdb_id = data.get("external_ids", {}).get('imdb_id')
            if imdb_id:
                imdb_data = self._fetch_data('tv', 'imdb', imdb_id)
                series.add_data(imdb_id, imdb_data, 'imdb')

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
            self.imdb_id = str(id)
        elif service == 'tmdb':
            self.tmdb_data = data
            self.tmdb_id = str(id)