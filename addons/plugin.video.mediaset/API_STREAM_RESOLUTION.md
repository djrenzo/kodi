# Mitele / Mediaset Infinity — API & Stream Resolution Reference

Reverse-engineered from `plugin.video.mediaset` (Kodi addon: `queries.py`, `default.py`,
`cookies.py`, `plugintools.py`). Written as a reference for building an equivalent
iOS client (AVPlayer/AVFoundation). None of this is officially documented by
Mediaset/Mitele — endpoints, payload shapes and persisted-query hashes can change
without notice.

This is a **private, undocumented API**. Treat everything here as reverse-engineered
and fragile: no versioning guarantees, no public docs, subject to breaking changes.

---

## 1. High-level flow

There are two independent subsystems:

1. **Browsing** — GraphQL API (`ottesp.api-graph.mediaset.it`) for programs, series,
   seasons, collections, episodes, search. Plus a **legacy "bitban" proxy API**
   (`mab.mediaset.es`) for older editorial listings (series/miniseries/documentales/music
   tabs) that predates the GraphQL rollout and is still used for some sections.
2. **Playback** — a multi-step handshake per video that ends in a signed, time-limited
   HLS URL. Live channels and VOD episodes use slightly different first steps but
   converge on the same token-signing flow (`cerbero.mediaset.es`).

```
Browsing:  GraphQL (ottesp.api-graph.mediaset.it)  ──or──  bitban proxy (mab.mediaset.es)
                              │
                              ▼
                    user picks a playable item
                              │
                              ▼
Playback:  resolve editorial id ─▶ resolve services config ─▶ resolve gbx/caronte
              ─▶ sign gid/gbx/bbx via Gigya ─▶ exchange for HTS token (cerbero)
              ─▶ build final playable URL + custom headers
```

---

## 2. Base URLs & constants

| Name | Value | Used for |
|---|---|---|
| `API_BASE` | `https://ottesp.api-graph.mediaset.it/` | GraphQL (persisted queries, GET with query-string) |
| `BITBAN_BASE` | `https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=` | Legacy editorial listing proxy |
| Gigya login | `https://login.mitele.es/accounts.getAccountInfo` | Session → signed identity (UID/UIDSignature) |
| Caronte (VOD services config) | dynamic, discovered per-video via `mab.mediaset.es` bitban proxy | VOD manifest + DRM metadata |
| Caronte (live channels) | `https://caronte.mediaset.es/delivery/channel/mmc/{slug}/mtweb` | Live manifest + DRM metadata |
| Cerbero (token exchange) | `https://cerbero.mediaset.es/` (POST) | Signs `gbx`+`bbx` into a playable query-string token |
| Live gbx | `https://mab.mediaset.es/1.0.0/get?oid=mtmw&eid=/api/mtmw/v3/gbx/mtweb/{slug}` | Live-only gbx token |
| Programdata (now/next EPG) | `https://services-ott-prod-fe.mediaset.net/esp/static/nownext/v3.0/nownext.json` | EPG data, no auth |

**GraphQL client identity**: the GraphQL requests declare themselves as an Apollo iOS
client:

```json
{"name": "apollo-ios", "version": "1.24.0"}
```

This is sent inside `extensions.clientLibrary` on every persisted-query request (see
§3). Mediaset's own iOS app is presumably an Apollo iOS client, so this identity
already matches what a real iOS client should send — useful groundwork for the app
you're building, but not a substitute for a real API key/session (see §4).

---

## 3. Session bootstrap (Gigya / SAP CDC)

Mediaset uses **Gigya (SAP Customer Data Cloud)** for identity. This addon carries a
captured, hardcoded guest/anonymous session rather than performing a real login flow.
`cookies.py` holds:

- `COOKIE` — a full captured Gigya redirect query string, from which `APIKey` and
  `login_token` (referred to as `SDK` in code) are extracted with a regex:
  `APIKey=(.*?)&sdk=js_latest&login_token=(.*?)&authMode=`.
- `GMID` — a Gigya `gmid`/`ucid` cookie pair, sent as a raw `Cookie` header on several
  requests.

These values expire / rotate periodically (Gigya sessions aren't indefinite) — for a
real app you'd want an actual Gigya web-login (or a registration/anonymous-session
call) rather than copy-pasting a captured cookie. The comments in `cookies.py`
reference `pastebin.com` raw pastes the original author used to keep a shared GMID
fresh — a sign this value does go stale and needs periodic refresh.

### Signing identity (`apiKeys` — cached ~2h)

```
GET https://login.mitele.es/accounts.getAccountInfo
    ?APIKey={APIKey}
    &sdk=js_latest
    &login_token={login_token}
    &format=json
Headers: Cookie: {GMID}; User-Agent: <desktop Chrome UA>
```

Response JSON gives:

```json
{ "UID": "...", "UIDSignature": "...", "signatureTimestamp": 1234567890 }
```

These three values are the **playback signing identity** — required on every stream
resolution (`payload.gid`, `payload.sig`, `payload.time` in §6). The addon caches them
in memory and only re-fetches if `time.time() > signatureTimestamp + 7200` (2 hours).
For iOS: cache the same way; don't call `accounts.getAccountInfo` per-playback.

---

## 4. GraphQL browsing API

`GET https://ottesp.api-graph.mediaset.it/?extensions={...}&variables={...}[&operationName=...]`

Persisted queries only — no raw GraphQL query text is ever sent, just a `sha256Hash`
identifying a query Mediaset's backend already knows. **You cannot invent new
queries**; you can only reuse the hashes this app (and presumably the real Mitele
apps) already use. If Mediaset invalidates a hash, that query breaks until a new hash
is captured (e.g. via a proxy on the official app/website).

### Request shape

```
extensions = {
  "clientLibrary": {"name": "apollo-ios", "version": "1.24.0"},
  "persistedQuery": {"sha256Hash": "<hash>", "version": 1}
}
variables = { ...query-specific... }
```

Both `extensions` and `variables` are JSON-encoded then URL-encoded as query
parameters.

### Known persisted queries

| Purpose | `sha256Hash` | `operationName` | Key variables |
|---|---|---|---|
| Paginated item listing (program list, collection episodes) | `744a87fb36dd66f089b2eb301bf12240fed77ba4d400fba3065fb8d6ff8535da` | — | `id` (ref_id), `after` (cursor), `first` (page size, int), `pagetype: "listing"`, `context` (fixed JSON string, see below) |
| Series page (seasons + collections) | `0cda6aecb759eed86ae38200c0ba3caabf0a1f7e0fa5197471fc62612e6b9eb4` | `MPlaySeriesPage` | `id` (series ref_id), `metadataTemplateName: "series-metadata-prod"`, `templateName: "series-page-prod"` |
| Search | `819f5ee79c4b589ce25bacbf2390d181311495e647bfff092a487b4e00552072` | — | `first`, `property: "search"`, `query` (search text), `uxReference: "filteredSearch"` |

`context` fixed value used for listing queries:
```json
{"a":{"flags":["SHOW_TITLE"],"layout":"GRID","template":"KEYFRAME_NOTEXT"},"pt":"listing"}
```

Standard headers for these GraphQL calls (`HEADERS1`):
```
User-Agent: <desktop Firefox UA>
x-m-platform: WEB
x-m-property: MITELE
```
Search additionally sends `x-m-user-context` (a base64-ish blob: `{"logged":true,"platform":"web"}`)
and `x-m-app-version: 1.0.20`.

### Response shapes

**Listing** (`query_ref_id` / `query_programs` / `query_episodes`):
```
data.result1.itemsConnection.items[]        // list of "cards"
data.result1.itemsConnection.pageInfo.hasNextPage
```
Can legitimately be `null` (empty collection) — handle that, not just empty arrays.

Each **item/card** (episode or program) roughly looks like:
```json
{
  "cardTitle": "...",
  "cardText": "...",
  "description": "...",
  "cardEditorialMetadata": "...",
  "cardEditorialMetadataRating": "...",
  "lastPublishDate": "2024-01-01T00:00:00Z",
  "duration": 1234,
  "durationString": "20:34",
  "cardImages": [{ "id": "...", "r": "..." }],
  "cardLink": { "referenceId": "...", "value": "<playable/programme URL>" }
}
```
- Episode thumbnail URL pattern:
  `https://img-prod-api2.mediasetplay.mediaset.it/api/images/mp/v5/esp/{image.id}/image_keyframe_poster/360/203?r={image.r}`
- `cardLink.value` is what gets passed into the playback pipeline (§6) as the
  "programa" URL — it's a `mitele.es`/`mediasetinfinity.es` page URL, not a media URL.

**Series page** (`query_series_page` / `query_seasons` / `query_collections`):
```
data.getSeriesPage.dataSource.seasons[]                              // list of seasons
data.getSeriesPage.areaContainersConnection.areaContainers[N]
    .areas[0].sections[0].collections[]                              // list of {id, title}
```
`N` (the area container index) isn't fixed — the addon walks `area=1,2,3...` until it
finds a container whose first collection has a `title` (some indices are decorative/empty).
Build the same fallback-scan logic rather than hardcoding an index.

**Search** (`query_search`):
```
data.getSearchPage.areaContainersConnection.areaContainers[0]
    .areas[0].sections[0].collections[0].itemsConnection.items[]
```
Same card shape as listings. Wrap in defensive key/index access — this path is deep
and any missing section returns an empty result rather than an error.

---

## 5. Legacy "bitban" proxy API (mab.mediaset.es)

Used for a few older sections (documentaries, miniseries episode tabs, music) that
aren't on the GraphQL API. `mab.mediaset.es` acts as a generic reverse proxy: you give
it a URL-encoded target path via `eid=`, it fetches it server-side and returns JSON
(with `Content-Type` sometimes mislabeled — expect to need manual `.json()` parsing
even when the response looks like HTML-escaped text).

- **Editorial index** (a-z listing pages):
  `GET {BITBAN_BASE}/automaticIndex/mtweb?url={target}&page={n}&id=a-z&size={size}`
- **Tabs listing** (miniseries episode tabs, paginated):
  `GET {BITBAN_BASE}/tabs/mtweb?url={target}&tabId={tag}&page={n}&size={size}`
  Pagination isn't in clean JSON fields — it's regex-extracted from the raw response
  body: `"actualPage":(\d+),"totalPages":(\d+)`. Budget for this being brittle.
- **Music / related items**: `GET {BITBAN_BASE}/related/mtweb?id={id}` → flat JSON array.
- **Legacy series ref_id normalization**: raw 6/7-digit editorial ids need an `MS`
  prefix zero-padded to a fixed width before being usable elsewhere:
  `len==6 → "MS000000"+id`, `len==7 → "MS00000"+id`.

Headers for all of the above (`HEADERS_SCRAPE`): a desktop Firefox UA + standard
`Accept`/`Accept-Language` — this is treated as a plain HTML/JSON scrape, not an
authenticated API call.

### Live channel list (`mediasetinfinity.es` homepage scrape)

There's no API for "list of live channels" — the addon scrapes the
`mediasetinfinity.es` homepage HTML for `href="/directo/{slug}/"` links, then looks
backward in a bounded window for the nearest image `src` and title `span`. This is
inherently fragile (breaks on any markup change) and **not recommended to port
as-is** — if Mediaset's iOS app calls a real endpoint for the channel list, prefer
reverse-engineering that instead of re-implementing HTML scraping in Swift. If no such
endpoint exists, hardcoding the known channel slugs (`telecinco`, `cuatro`, etc.) is
more maintainable than scraping.

---

## 6. VOD stream resolution (the important part)

Given a `cardLink.value` programme page URL, resolving it to a playable manifest is a
5-step chain. All of these are server round-trips — do this once when the user taps
"play", not ahead of time.

```
programme URL
   │  (normalize domain: mediasetinfinity.es → mitele.es)
   ▼
1) GET mab.mediaset.es bitban proxy → dataEditorialId
   /v2/prePlayer/mtand?url={programmeUrl}
   → response.video.dataEditorialId
   │
   ▼
2) GET mab.mediaset.es bitban_api proxy → services config
   /api/v2/mitele/videos/{dataEditorialId}/config/final.json?platform=mtand
   → response.services  (dict of named service URLs, incl. "gbx" and "caronte")
   │
   ▼
3a) GET services.gbx        → response.gbx                (a token string)
3b) GET services.caronte    → caronte JSON:
        caronte.dls[0].stream    → "picky" (FairPlay-DRM HLS manifest URL)
        caronte.bbx               → "bbx" token
        caronte.subtitles[]        → [{ "vtt": "<url>" }, ...] (optional)
   │
   ▼
4) Sign with Gigya identity (§3, cached):
   payload = { "gid": UID, "time": signatureTimestamp,
               "sig": UIDSignature, "gbx": gbx, "bbx": bbx }
   POST cerbero.mediaset.es  (JSON body)
   → response.tokens["1"].cdn   → "hts" (a URL query-string token, NOT url-encoded — append as-is)
   │
   ▼
5) Build final URL:
   picky = picky.replace("hls-fairplay.ism", "main.ism")   // drop FairPlay variant, use plain HLS
   final_url = f"{picky}?{hts}"
```

Headers used at each step:
- Steps 1–2 (`mab.mediaset.es` calls): `HEADER2` = `{"Cookie": GMID, "User-Agent": <desktop Chrome UA>}`.
- Step 3a/3b (`gbx`/`caronte` URLs — these are on `mediaset.es`/CDN infra, not
  `mab.mediaset.es`): `GBX_HEADER` = desktop Chrome UA + `Referer`/`Origin: https://www.mediaset.es`.
- Step 4 (`cerbero.mediaset.es`): `HEADER4` = `{"Accept-Encoding":"gzip","Accept":"application/json, text/plain, */*","Origin":"app.mitele.android.es","User-Agent":"MOBILE/6.13.2(2108)","Content-Type":"application/json;charset=UTF-8"}`.
  Note this is an **Android app UA/Origin**, not the desktop UA used elsewhere — cerbero
  appears to validate this is a "real app" call. For an iOS client you'd likely want to
  capture the real iOS app's UA/Origin here instead of reusing the Android one, in case
  cerbero starts checking platform consistency.
- Final playback request: `PLAY_HEADERS` = `{"user-agent": <desktop Chrome UA>, "referer": "https://www.mediasetinfinity.es/"}`.
  These are the headers the HLS **manifest and segment requests** must carry — not just
  the initial request.

### DRM note

`caronte.dls[0].stream` points at a **FairPlay-protected** manifest
(`hls-fairplay.ism`). This code sidesteps FairPlay entirely by string-replacing it for
the plain `main.ism` variant, which serves clear (non-DRM) HLS. This only works because
Mediaset happens to also expose an unencrypted variant behind the same signed token —
it is not a DRM bypass of the encrypted stream itself. If Mediaset ever removes the
clear variant, this whole approach breaks and a real FairPlay implementation
(`AVContentKeySession`, an FPS certificate + license server) would be required instead.
Keep this in mind for the iOS port: **this document does not cover real FairPlay DRM**,
only the clear-HLS shortcut this addon relies on.

---

## 7. Live channel stream resolution

Similar chain, shorter, and slug-based (`slug` = e.g. `telecinco`, `cuatro`,
`factoria-de-ficcion`, from the channel-list scrape in §5):

```
1) GET https://caronte.mediaset.es/delivery/channel/mmc/{slug}/mtweb   (HEADER2)
   → dls[0].stream → picky
   → bbx           → bbx
   → subtitles      → subs (optional)

2) GET https://mab.mediaset.es/1.0.0/get?oid=mtmw&eid=/api/mtmw/v3/gbx/mtweb/{slug}   (HEADER2)
   → response.gbx  → gbx

3) Same Gigya-signed cerbero exchange as VOD step 4 → hts

4) Same final URL + FairPlay→main.ism swap as VOD step 5, same PLAY_HEADERS.
```

---

## 8. Non-Mediaset direct-play fallback (RTVE)

Two hardcoded channels (RTVE La 1 / La 2) bypass the whole pipeline — they're public
HLS URLs with no token/DRM step at all:
```
https://rtvelivestream.rtve.es/rtvesec/la1/la1_main_dvr_720.m3u8
https://rtvelivestream.rtve.es/rtvesec/la2/la2_main_dvr_720.m3u8
```
Headers: `PLAY_HEADERS_RTVE` = `{"User-Agent": <desktop Firefox UA>, "Referer": "https://www.rtve.es/", "Origin": "https://www.rtve.es"}`.
Play as-is; no signing needed.

---

## 9. Mapping "play with custom headers" to iOS/AVFoundation

Kodi's convention is to suffix the playable URL with `|header1=value1&header2=value2`
(URL-encoded), which `plugintools.play_resolved_url` builds via:
```python
url = f"{url}|{'&'.join(f'{k}={v}' for k, v in headers.items())}"
```
That pipe-suffix is Kodi-specific — **do not send it to AVPlayer**. On iOS, set the
same headers via `AVURLAsset`:

```swift
let headers = [
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "referer": "https://www.mediasetinfinity.es/"
]
let asset = AVURLAsset(url: manifestURL, options: [
    "AVURLAssetHTTPHeaderFieldsKey": headers
])
let item = AVPlayerItem(asset: asset)
```
Note `AVURLAssetHTTPHeaderFieldsKey` only reliably applies to the **initial manifest
request** for HLS in some iOS versions — segment/key requests may not inherit it
automatically. If segments 403 without the header, you'll need a custom
`AVAssetResourceLoaderDelegate` to re-attach headers per-request, or confirm the CDN
doesn't actually check headers on segment URLs (many only check them on the manifest).

Subtitles (`caronte.subtitles[].vtt` / `resp.subtitles`) are plain WebVTT URLs — load
directly as an `AVMediaSelectionOption` / out-of-band `AVPlayerItem` text track, no
special auth needed based on this code (no headers are attached to subtitle fetches
here).

---

## 10. Fragility / things to watch when porting

- **Persisted query hashes (§4)** are opaque and can be invalidated by Mediaset at any
  time; you can only discover new ones by capturing real app/web traffic.
- **Gigya session (§3)** is a captured, hardcoded cookie/token pair with no visible
  refresh mechanism in this code — for production use, implement a real Gigya
  login/registration flow rather than hardcoding a session that will eventually expire.
- **HTML scraping (§5, channel list)** breaks on any markup change; treat as last resort.
- **Cerbero's Android UA/Origin (§6 step 4)** is a mismatch already baked into this
  addon (desktop everywhere else, Android here) — worth testing whether cerbero
  actually validates platform consistency before copying this as-is into an iOS app;
  may be safer to send a real iOS UA/Origin there instead.
- **Clear-HLS shortcut (§6 DRM note)** is not real DRM handling — it works only as long
  as Mediaset keeps serving an unencrypted variant beside the FairPlay one.
- Several response paths use **deep, unguarded dict chains** in the Python source
  (`data.get(...).get(...)...`) — the working assumption is "if a field is missing,
  the feature/section legitimately doesn't exist for this item" (e.g. `itemsConnection`
  can be `null` for empty collections). Mirror that defensively in Swift with optional
  chaining rather than force-unwraps.
