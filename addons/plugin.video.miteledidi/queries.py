import requests
from urllib.parse import urlencode
from json import dumps
from cookies import get_cookies
import time

KEY, SDK, GMID = get_cookies()

API_BASE = "https://ottesp.api-graph.mediaset.it/"

CLIENTLIB = {
    "name": "apollo-ios",
    "version": "1.24.0"}

## HEADERS ##
HEADERS1 = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0",
                "x-m-platform": "WEB",
                "x-m-property": "MITELE"
            }

HEADER2 = {
        "Cookie": GMID,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36"
        }

GBX_HEADER = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.mediaset.es/",
            "Origin": "https://www.mediaset.es"
        }

HEADER4 = {
        'Accept-Encoding':'gzip',
        'Accept':'application/json, text/plain, */*',
        'Origin':'app.mitele.android.es',
        'User-Agent':'MOBILE/6.13.2(2108)',
        'Content-Type':'application/json;charset=UTF-8'
        }

PLAY_HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "referer": "https://www.mediasetinfinity.es/"
    }
  
PLAY_HEADERS_RTVE = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0",
        "Referer": "https://www.rtve.es/",
        "Origin": "https://www.rtve.es"
        }

## HEADERS ##

def gen_persistedQuery(pq):
  return {"sha256Hash": pq,
          "version": 1}


def gen_extensions(pq):
  return {
    "clientLibrary": CLIENTLIB,
    "persistedQuery": gen_persistedQuery(pq)}

## BASE QUERIES ##
def query_ref_id(ref_id, after="", limit=100):
    limit = int(limit)
    context_string_required = r'{"a":{"flags":["SHOW_TITLE"],"layout":"GRID","template":"KEYFRAME_NOTEXT"},"pt":"listing"}'

    variables_data = {
        "id": ref_id,
        "after": after,
        "first": limit,
        "pagetype": "listing",
        "context": context_string_required
        }
    extensions_data = gen_extensions("744a87fb36dd66f089b2eb301bf12240fed77ba4d400fba3065fb8d6ff8535da")

    encoded_query = urlencode({
        'extensions': dumps(extensions_data),
        'variables': dumps(variables_data)})

    return requests.get(
        f"{API_BASE}?{encoded_query}",
        headers=HEADERS1)

def query_series_page(ref_id):
  variables_data = {
    "id": ref_id,
    "metadataTemplateName":"series-metadata-prod",
    "templateName":"series-page-prod"
  }

  extensions_data = gen_extensions("0cda6aecb759eed86ae38200c0ba3caabf0a1f7e0fa5197471fc62612e6b9eb4")

  encoded_query = urlencode({
      'extensions': dumps(extensions_data),
      "operationName": "MPlaySeriesPage",
      'variables': dumps(variables_data)
      })
  
  return requests.get(
      f"{API_BASE}?{encoded_query}",
      headers=HEADERS1
      )

## REFINED QUERIES ##

def query_programs(code, after="", limit=10):
    if isinstance(after, int):
        after = str(after)
    if after == "0":
        after = ""

    r = query_ref_id(ref_id=code, after=after, limit=limit).json()
    itemsConnection = (r.get("data")
                        .get("result1")
                        .get("itemsConnection"))

    return (itemsConnection.get("items"), itemsConnection.get("pageInfo"))

def query_seasons(series_id):
  r = query_series_page(ref_id=series_id).json()
  return r.get("data") \
          .get("getSeriesPage") \
          .get("dataSource") \
          .get("seasons")

def query_collections(season_id):
  r = query_series_page(ref_id=season_id).json()
  collections = r.get("data") \
                    .get("getSeriesPage") \
                    .get("areaContainersConnection") \
                    .get("areaContainers")[1] \
                    .get("areas")[0] \
                    .get("sections")[1] \
                    .get("collections")

  return [{"title": c.get("title"), "id": c.get("id")} for c in collections]

def query_episodes(collection_id, after="", limit=10):
    if isinstance(after, int):
        after = str(after)
    if after == "0":
        after = ""

    r = query_ref_id(ref_id=collection_id, after=after, limit=limit).json()
    itemsConnection = (r.get("data")
                        .get("result1")
                        .get("itemsConnection"))

    return (itemsConnection.get("items"), itemsConnection.get("pageInfo"))


def get_data_editorial_id(programa):
    req1 = requests.get(
        f'https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2Fv2%2FprePlayer%2Fmtand%3Furl%3D{programa}',
        headers=HEADER2).json()

    return req1.get("video").get("dataEditorialId")


def get_services(data_editorial_id):
    services = requests.get(
        f'https://mab.mediaset.es/1.0.0//get?oid=bitban_api&eid=%2Fapi%2Fv2%2Fmitele%2Fvideos%2F{data_editorial_id}%2Fconfig%2Ffinal.json%3Fplatform%3Dmtand',
        headers=HEADER2).json()
    
    return services.get("services")

def get_gbx_picky(services):
    gbx_temp = requests.get(services.get("gbx"), headers=GBX_HEADER)
    gbx = gbx_temp.json().get("gbx")
    caronte = requests.get(services.get("caronte"), headers=GBX_HEADER).json()
    picky = caronte.get("dls")[0].get("stream")
    bbx = caronte.get("bbx")

    return (gbx_temp, gbx, caronte, picky, bbx)

def get_hts(payload):
    url8 = requests.post(
        'https://cerbero.mediaset.es/',
        headers=HEADER4,
        json=payload
        )

    return url8.json().get("tokens").get("1").get("cdn")

def gen_play_headers(headers):
    return "&".join([f"{x}={y}" for x,y in headers.items()])

class apiKeys:
  def __init__(self):
    self.UID = None
    self.UIDSignature = None
    self.signatureTimestamp = None
    self.threshold = 2 * 60 * 60 # 2 hours for now
  
  def _gen_api_keys(self):
    print("generating")
    apikey_resp = requests.get(
        f'https://login.mitele.es/accounts.getAccountInfo?APIKey={KEY}&sdk=js_latest&login_token={SDK}&format=json',
        headers=HEADER2)
    apikey = apikey_resp.json()
    return (apikey.get('UID'), apikey.get('UIDSignature'), apikey.get('signatureTimestamp'))

  def get_api_keys(self):
    if self.UID and self.UIDSignature and self.signatureTimestamp:
      if time.time() <= int(self.signatureTimestamp) + self.threshold:
        print(f"Diff {time.time() - int(self.signatureTimestamp)} seconds have passed")
        return (self.UID, self.UIDSignature, self.signatureTimestamp)

      print(f"More than {self.threshold} seconds have passed")
  
    self.UID, self.UIDSignature, self.signatureTimestamp = self._gen_api_keys()
    return (self.UID, self.UIDSignature, self.signatureTimestamp)
    
def get_programdata():
  return requests.get("https://services-ott-prod-fe.mediaset.net/esp/static/nownext/v3.0/nownext.json") \
                .json() \
                .get("response") \
                .get("listings")

def get_current_program(programdata, name):
  return programdata.get(name).get("currentListing").get("mediasetlisting$epgTitle")