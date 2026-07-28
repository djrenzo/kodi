from abc import ABC, abstractmethod
from urllib.parse import urlencode

from torbox_common import log
from torbox_http import download, fetch_json

WYZIE_API = 'https://sub.wyzie.io/search'
WYZIE_KEY = 'wyzie-gvo9qomam6re1xxww2krz89m7f0ww4ax'
WYZIE_LIMIT = 10
OPENSUBTITLES_API = 'https://subs5.strem.io/en/download/subencoding-stremio-utf8/src-api/file/{}'
OPENSUBTITLES_SEARCH_API = 'https://opensubtitles-v3.strem.io/subtitles/movie/{}/filename=t.json'


class SubtitleFetcher(ABC):
    """Abstract base class for subtitle fetchers."""

    @abstractmethod
    def fetch_subtitles(self, tmdb_id, language='en', season=None, episode=None):
        """Fetch subtitles for the given parameters."""
        pass

    def get_subtitle_url(self, opensubtitles_id):
        """Construct the subtitle download URL for the given OpenSubtitles ID."""
        opensubtitles_id = str(opensubtitles_id)
        return OPENSUBTITLES_API.format(opensubtitles_id)

    def download(self, opensubtitles_id, dest_path):
        """Download subtitle file from the given URL.
        
        Args:
            opensubtitles_id: ID of the subtitle to download
            dest_path: Destination file path to save the subtitle
            
        Returns:
            True if download was successful, False otherwise
        """
        opensubtitles_id = str(opensubtitles_id)
        log('Downloading subtitle: {}'.format(opensubtitles_id))
        subtitle_url = self.get_subtitle_url(opensubtitles_id)
        return download(subtitle_url, dest_path)

    def download_url(self, subtitles_url, dest_path):
        """Download subtitle file from the given URL."""
        log('Downloading subtitle: {}'.format(subtitles_url))
        return download(subtitles_url, dest_path)


class WyzieFetcher(SubtitleFetcher):
    """Wyzie subtitle fetcher implementation."""

    def __init__(self, api_url=WYZIE_API, api_key=WYZIE_KEY, limit=WYZIE_LIMIT):
        self.api_url = api_url
        self.api_key = api_key
        self.limit = limit

    def fetch_subtitles(self, tmdb_id, language='en', season=None, episode=None):
        """Fetch subtitles from Wyzie API."""
        params_data = {'id': str(tmdb_id), 'format': 'srt', 'language': language, 'key': self.api_key}
        if season is not None:
            params_data['season'] = int(season)
        if episode is not None:
            params_data['episode'] = int(episode)

        params = urlencode(params_data)
        url = '{}?{}'.format(self.api_url, params)

        data = fetch_json(url)
        return data[:self.limit] if isinstance(data, list) else []


class OpenSubtitlesFetcher(SubtitleFetcher):
    """OpenSubtitles subtitle fetcher implementation."""

    def __init__(self, api_url=OPENSUBTITLES_SEARCH_API):
        self.api_url = api_url

    def fetch_subtitles(self, imdb_id, language='eng'):
        """Fetch subtitles from OpenSubtitles API."""
        imdb_id = str(imdb_id)
        url = self.api_url.format(imdb_id)
        data = fetch_json(url).get('subtitles', [])
        return [sub for sub in data if sub.get('lang') == language]

    def fetch_subtitles_urls(self, imdb_id, language='eng'):
        """Fetch subtitle URLs from OpenSubtitles API."""
        imdb_id = str(imdb_id)
        subtitles = self.fetch_subtitles(imdb_id, language)
        return [sub.get('url') for sub in subtitles]