from urllib.request import Request, urlopen
from urllib.parse import urlencode
import json

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

# Wikidata properties differ between TV series and movies.
MEDIA_PROPERTIES = {
    "tv": {
        "tmdb": "P4983",  # TMDB TV series ID
        "tvdb": "P4835",  # TheTVDB series ID
    },
    "movie": {
        "tmdb": "P4947",   # TMDB movie ID
        "tvdb": "P12196",  # TheTVDB movie ID
    },
}

QUERY_TEMPLATE = """
SELECT ?show ?showLabel ?imdbID ?tvdbID WHERE {{
  VALUES ?tmdbID {{ "{tmdb_id}" }}

  ?show wdt:{tmdb_prop} ?tmdbID.

  OPTIONAL {{ ?show wdt:P345 ?imdbID. }}          # IMDb ID
  OPTIONAL {{ ?show wdt:{tvdb_prop} ?tvdbID. }}

  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def get_ids_from_tmdb(tmdb_id: str, media_type: str = "tv", timeout: int = 30) -> list[dict]:
    """
    media_type: "tv" or "movie"
    """
    if media_type not in MEDIA_PROPERTIES:
        raise ValueError(f"media_type must be one of {list(MEDIA_PROPERTIES)}, got {media_type!r}")

    props = MEDIA_PROPERTIES[media_type]
    query = QUERY_TEMPLATE.format(
        tmdb_id=tmdb_id,
        tmdb_prop=props["tmdb"],
        tvdb_prop=props["tvdb"],
    )

    normalized_url = f"{WIKIDATA_SPARQL_URL}?{urlencode({'query': query})}"

    request_headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "MyApp/1.0 (mailto:didier.renzo@gmail.com)",
    }

    req = Request(normalized_url, data=None, headers=request_headers, method="GET")
    response = urlopen(req, timeout=timeout)
    raw = response.read()

    data = json.loads(raw)
    results = []
    for binding in data["results"]["bindings"]:
        results.append({
            "wikidata_id": binding["show"]["value"].rsplit("/", 1)[-1],
            "label": binding.get("showLabel", {}).get("value"),
            "imdb_id": binding.get("imdbID", {}).get("value"),
            "tvdb_id": binding.get("tvdbID", {}).get("value"),
        })
    return results[0] if results else None