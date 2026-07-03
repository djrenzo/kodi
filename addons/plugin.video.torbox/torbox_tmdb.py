import re
from html import unescape
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

import xbmc
import xbmcgui

from torbox_common import log

TMDB_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJlMDUxYjA5Nzc5Y2JiNDI1NjUyMmNhYjQzZTE4YzY1NSIsIm5iZiI6MTc3NTIzNzAxMC43NDg5OTk4LCJzdWIiOiI2OWNmZjc5Mjg4ZjBhMDQ1NDRkMjk4N2YiLCJzY29wZXMiOlsiYXBpX3JlYWQiXSwidmVyc2lvbiI6MX0.igCod8FKscZMklnvK9oiyfFMjy0Eyym50sGrj0knX4c"

TMDB_SEARCH_MOVIE_URL = 'https://www.themoviedb.org/search/movie'
TMDB_SEARCH_TV_URL = 'https://www.themoviedb.org/search/tv'
TMDB_RESULT_LIMIT = 10

_CARD_START_RE = re.compile(r'data-object-id="[^"]+"')
_POSTER_SRC_RE = re.compile(r'https://media\.themoviedb\.org/t/p/w\d+_and_h\d+_face(?P<path>/[^\s"]+)')
_PLOT_RE = re.compile(r'class="mt-4[^>]*>\s*<p>(?P<plot>.*?)</p>', re.DOTALL)
_POSTER_BASE = 'https://media.themoviedb.org/t/p/w500'
_TITLE_RE = re.compile(r'<h2[^>]*>(?P<title_html>.*?)</h2>', re.DOTALL)
_DATE_RE = re.compile(r'<span class="release_date[^"]*"[^>]*>(?P<date_html>.*?)</span>', re.DOTALL)
_TAG_RE = re.compile(r'<[^>]+>')
_SPACE_RE = re.compile(r'\s+')
_YEAR_RE = re.compile(r'\b(?:19|20)\d{2}\b')


def _clean_html_text(value):
    text = _TAG_RE.sub(' ', value or '')
    text = unescape(text)
    return _SPACE_RE.sub(' ', text).strip()


def _search_tmdb(title, year=None, limit=TMDB_RESULT_LIMIT, search_url=TMDB_SEARCH_MOVIE_URL, media_type='movie'):
    query = (title or '').strip()
    if not query:
        return []

    if year:
        query = '{} y:{}'.format(query, year)

    url = '{}?{}'.format(search_url, urlencode({'query': query}))
    log('TMDB search query: {}'.format(url))

    try:
        req = Request(
            url,
            headers={
                'User-Agent': 'Kodi/TorBox-Plugin',
                'Accept-Language': 'en-US,en;q=0.8',
            },
        )
        response = urlopen(req, timeout=20)
        html = response.read().decode('utf-8', errors='ignore')
    except Exception as exc:
        log('TMDB search error: {}'.format(exc), xbmc.LOGWARNING)
        return []

    results = []
    seen_ids = set()
    id_re = re.compile(r'href="/{}/(?P<id>\d+)(?:-[^"]*)?"'.format(media_type))

    card_starts = [match.start() for match in _CARD_START_RE.finditer(html)]
    card_starts.append(len(html))

    for index in range(len(card_starts) - 1):
        chunk = html[card_starts[index]:card_starts[index + 1]]

        id_match = id_re.search(chunk)
        if not id_match:
            continue

        movie_id = id_match.group('id')
        if movie_id in seen_ids:
            continue

        title_match = _TITLE_RE.search(chunk)
        if not title_match:
            continue

        movie_title = _clean_html_text(title_match.group('title_html'))
        if not movie_title:
            continue

        date_match = _DATE_RE.search(chunk)
        release_text = _clean_html_text(date_match.group('date_html')) if date_match else ''
        year_match = _YEAR_RE.search(release_text)

        poster_path_match = _POSTER_SRC_RE.search(chunk)
        poster_url = '{}{}'.format(_POSTER_BASE, poster_path_match.group('path')) if poster_path_match else ''

        plot_match = _PLOT_RE.search(chunk)
        plot = _clean_html_text(plot_match.group('plot')) if plot_match else ''

        results.append(
            {
                'id': movie_id,
                'title': movie_title,
                'year': int(year_match.group(0)) if year_match else None,
                'poster_url': poster_url,
                'plot': plot,
            }
        )
        seen_ids.add(movie_id)

        if len(results) >= max(1, limit):
            break

    return results


def search_tmdb_movies(title, year=None, limit=TMDB_RESULT_LIMIT):
    return _search_tmdb(title, year=year, limit=limit, search_url=TMDB_SEARCH_MOVIE_URL, media_type='movie')


def search_tmdb_tvshows(title, year=None, limit=TMDB_RESULT_LIMIT):
    return _search_tmdb(title, year=year, limit=limit, search_url=TMDB_SEARCH_TV_URL, media_type='tv')


def get_tvdb_id_from_tmdb(tmdb_id, media_type: str = "tv"):
    """
    Return the TVDB ID for a given TMDB ID, or None if not found.
 
    Args:
        tmdb_id: The TMDB ID of the show (or movie).
        api_key: Your TMDB v3 API key.
        media_type: "tv" for TV shows (default) or "movie" for movies.
                    Note: movies don't have TVDB IDs in TMDB's system;
                    this only makes sense for media_type="tv".
 
    Returns:
        The TVDB ID as an int, or None if TMDB has no TVDB ID on file
        (or the TMDB ID doesn't exist).
 
    Raises:
        urllib.error.HTTPError: if the request fails (e.g. invalid API key,
                                 TMDB ID not found -> 404).
    """
    try:
        query = urlencode({"api_key": TMDB_KEY})
        url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/external_ids?{query}"
    
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        dialog = xbmcgui.Dialog()
        dialog.ok(str(data))
    
        tvdb_id = data.get("tvdb_id")

        if tvdb_id is not None:
            return tvdb_id

        log('TVDB ID not found for TMDB ID: {}'.format(tmdb_id), xbmc.LOGWARNING)
        return None

    except Exception as exc:
        log('Error fetching TVDB ID from TMDB: {}'.format(exc), xbmc.LOGWARNING)
        return None