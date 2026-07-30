import html
import re
from html import unescape
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmc

from torbox_common import get_tmdb_key, log
from torbox_http import fetch_json, http_req
from torbox_sparql import get_ids_from_tmdb

TMDB_API = "https://api.themoviedb.org/3/{media_type}/{tmdb_id}/external_ids"
IMDB_API = "https://v3-cinemeta.strem.io/meta/{media_type}/{imdb_id}.json"
IMDB_SEARCH_API = "	https://v3-cinemeta.strem.io/catalog/{media_type}/top/search={query}.json"
TMDB_SEARCH_MOVIE_URL = 'https://www.themoviedb.org/search/movie'
TMDB_SEARCH_TV_URL = 'https://www.themoviedb.org/search/tv'
TMDB_RESULT_LIMIT = 10
IMDB_RESULT_LIMIT = 10

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


def _search_imdb(title, year=None, limit=IMDB_RESULT_LIMIT, search_url=IMDB_SEARCH_API, media_type='movie'):
    query = (title or '').strip()
    if not query:
        return []

    url = search_url.format(media_type=media_type, query=urlencode(query))
    log('IMDB search query: {}'.format(url))

    data = fetch_json(url)
    if not data:
        return []
    
    results = data.get("metas", [])

    if len(results) > limit:
        results = results[:limit]

    return [{
                'id': r.get("imdb_id"),
                'title': r.get("name"),
                'year': r.get("releaseInfo")[:4] if r.get("releaseInfo") else None,
                'poster_url': r.get("poster"),
                'plot': r.get("name"),
            } for r in results]


def search_tmdb_movies(title, year=None, limit=TMDB_RESULT_LIMIT):
    return _search_tmdb(title, year=year, limit=limit, search_url=TMDB_SEARCH_MOVIE_URL, media_type='movie')


def search_tmdb_tvshows(title, year=None, limit=TMDB_RESULT_LIMIT):
    return _search_tmdb(title, year=year, limit=limit, search_url=TMDB_SEARCH_TV_URL, media_type='tv')


def search_imdb_movies(title, year=None, limit=IMDB_RESULT_LIMIT):
    return _search_imdb(title, year=year, limit=limit, search_url=IMDB_SEARCH_API, media_type='movie')


def search_imdb_tvshows(title, year=None, limit=IMDB_RESULT_LIMIT):
    return _search_imdb(title, year=year, limit=limit, search_url=IMDB_SEARCH_API, media_type='series')

def parse_tmdb_season(season_match):
    r = re.findall(r'<a href="([^"]+)">.*?<img[^>]*\ssrc="([^"]+)"', season_match, re.DOTALL)
    if r:
        season, url = tuple(*r)
        return season.split("/")[-1], url.split("/")[-1]
    return (None, None)

def query_imdb_title(title):
    query = f"https://v3.sg.media-imdb.com/suggestion/x/{title}.json?includeVideos=1"
    data = fetch_json(query).get("d")
    return data

def get_tmbd_seasons(tmdb_id):
    url = "https://www.themoviedb.org/tv/{tmdb_id}/seasons".format(tmdb_id=tmdb_id)
    r = http_req(url)
    if not r:
        log('Failed to fetch TMDB seasons for ID: {}'.format(tmdb_id), xbmc.LOGWARNING)
        return {}
    html = r.decode('utf-8', errors='ignore')
    
    season_matches = re.findall(r'<div class="season"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not season_matches:
        log('No seasons found for TMDB ID: {}'.format(tmdb_id), xbmc.LOGWARNING)
        return {}
  
    seasons = {}
    for sm in season_matches:
        parsed_season, parsed_url = parse_tmdb_season(sm)
        if parsed_season:
            seasons[parsed_season] = parsed_url
    return seasons

def get_external_id_from_tmdb(
    tmdb_id,
    media_type: str = "tv" or "movie" or "series",
    external_source: str | Iterable[str] = "tvdb_id",
) -> str | dict[str, str | None] | None:
    """
    Return one or more external IDs for a given TMDB ID.
 
    Args:
        tmdb_id: The TMDB ID of the show (or movie).
        media_type: "tv" for TV shows (default) or "movie" for movies.
        external_source: A single external field (e.g. "tvdb_id") or an
                 iterable of fields (e.g. ["tvdb_id", "imdb_id"]).
 
    Returns:
        If external_source is a string, returns that value as string or None.
        If external_source contains multiple fields, returns a dict where each
        requested field maps to a string value or None.
 
    Raises:
        urllib.error.HTTPError: if the request fails (e.g. invalid API key,
                                 TMDB ID not found -> 404).
    """
    
    if media_type == "series":
        media_type = "tv"

    if isinstance(external_source, str):
        requested_sources = [external_source]
        multi = False
    else:
        requested_sources = [src for src in external_source if src]
        multi = True

    if not requested_sources:
        return {} if multi else None

    try:
        tmdb_key = get_tmdb_key(notify=True)
        tmdb_id = str(tmdb_id)

        if not tmdb_key:
            log('TMDB key is empty; configure providers first', xbmc.LOGWARNING)
            data = get_ids_from_tmdb(tmdb_id, media_type=media_type, timeout=30)
            
        else:
            url = TMDB_API.format(media_type=media_type, tmdb_id=tmdb_id)
            data = fetch_json(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {tmdb_key}",
                },
            )

        if data is None:
            log('No data returned from TMDB for TMDB ID: {}'.format(tmdb_id), xbmc.LOGWARNING)
            return {} if multi else None

        if multi or len(requested_sources) > 1:
            result = {}
            for source in requested_sources:
                value = data.get(source)
                result[source] = str(value) if value is not None else None
            return result

        source = requested_sources[0]
        ext = data.get(source)

        if ext is not None:
            return str(ext)

        log('{} ID not found for TMDB ID: {}'.format(source.upper(), tmdb_id), xbmc.LOGWARNING)
        return None

    except Exception as exc:
        field_text = ','.join(requested_sources).upper()
        log('Error fetching {} ID from TMDB: {}'.format(field_text, exc), xbmc.LOGWARNING)
        return {} if multi else None


def get_external_id_from_imdb(imdb_id, media_type: str = "tv" or "movie", external_source: str = "tvdb_id" or "tmdb_id") -> str | None:
    if media_type == "tv":
        media_type = "series"

    if external_source == "tmdb_id":
        external_source = "moviedb_id"

    try:
        imdb_id = str(imdb_id)
        url = IMDB_API.format(media_type=media_type, imdb_id=imdb_id)
        data = fetch_json(url)

        if data is None:
            log('No data returned from IMDB for IMDB ID: {}'.format(imdb_id), xbmc.LOGWARNING)
            return None

        ext = data.get(external_source)

        if ext is not None:
            return str(ext)

        log('{} ID not found for IMDB ID: {}'.format(external_source.upper(), imdb_id), xbmc.LOGWARNING)
        return None

    except Exception as exc:
        log('Error fetching {} ID from IMDB: {}'.format(external_source.upper(), exc), xbmc.LOGWARNING)
        return None