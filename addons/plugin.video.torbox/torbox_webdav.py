import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse, urlunparse
from urllib.request import Request, urlopen

import xbmc
import xbmcgui

from torbox_common import APP_NAME, WebDavItem, log, make_auth_header
from torbox_text import NOTIFY_CONNECTION_FAILED, NOTIFY_HTTP_ERROR


def encode_webdav_url(url):
    parsed = urlparse(url)
    safe = "/:@!$&'()*+,;=-._~%"
    encoded_path = quote(unquote(parsed.path), safe=safe)
    return urlunparse(
        (parsed.scheme, parsed.netloc, encoded_path, parsed.params, parsed.query, parsed.fragment)
    )


def propfind(url, username, password, depth=1):
    body = b'''<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
  <prop>
    <resourcetype/>
    <getcontentlength/>
    <getlastmodified/>
    <displayname/>
    <getcontenttype/>
  </prop>
</propfind>'''

    safe_url = encode_webdav_url(url)
    log('PROPFIND: {}'.format(safe_url))

    headers = {
        'Authorization': make_auth_header(username, password),
        'Depth': str(depth),
        'Content-Type': 'application/xml; charset=utf-8',
        'User-Agent': 'Kodi/TorBox-Plugin',
    }

    req = Request(safe_url, data=body, headers=headers, method='PROPFIND')

    try:
        response = urlopen(req, timeout=30)
        return ET.fromstring(response.read())
    except HTTPError as exc:
        log('PROPFIND HTTP {}: {}'.format(exc.code, url), xbmc.LOGERROR)
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_HTTP_ERROR.format(exc.code), xbmcgui.NOTIFICATION_ERROR)
    except URLError as exc:
        log('PROPFIND URLError {}: {}'.format(exc.reason, url), xbmc.LOGERROR)
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_CONNECTION_FAILED, xbmcgui.NOTIFICATION_ERROR)
    except ET.ParseError as exc:
        log('PROPFIND XML parse error: {}'.format(exc), xbmc.LOGERROR)
    except Exception as exc:
        log('PROPFIND unexpected error: {}'.format(exc), xbmc.LOGERROR)

    return None


def parse_propfind(xml_root, base_url, current_path):
    if xml_root is None:
        return []

    ns = {'d': 'DAV:'}
    items = []
    decoded_current = unquote(current_path).rstrip('/')

    for response in xml_root.findall('.//d:response', ns):
        href_el = response.find('d:href', ns)
        if href_el is None or not href_el.text:
            continue

        href = href_el.text.strip()
        path = urlparse(href).path
        if not path:
            continue

        if unquote(path).rstrip('/') == decoded_current:
            continue

        resourcetype = response.find('.//d:resourcetype', ns)
        is_collection = resourcetype is not None and resourcetype.find('d:collection', ns) is not None

        displayname_el = response.find('.//d:displayname', ns)
        displayname = displayname_el.text if displayname_el is not None and displayname_el.text else None

        size_el = response.find('.//d:getcontentlength', ns)
        if size_el is not None and size_el.text:
            try:
                size = int(size_el.text)
            except (TypeError, ValueError):
                size = 0
        else:
            size = 0

        name = displayname or unquote(path.rstrip('/').split('/')[-1])
        if not name:
            continue

        parsed_base = urlparse(base_url)
        full_url = '{}://{}{}'.format(parsed_base.scheme, parsed_base.netloc, path)

        items.append(
            WebDavItem(
                name=name,
                full_url=full_url,
                path=path,
                is_collection=is_collection,
                size=size,
            )
        )

    return items


def build_authed_url(stream_url, username, password):
    parsed = urlparse(stream_url)
    if not parsed.scheme or not parsed.netloc or not parsed.hostname:
        return stream_url

    user = quote(username, safe='')
    passwd = quote(password, safe='')
    netloc = '{}:{}@{}'.format(user, passwd, parsed.hostname)
    if parsed.port:
        netloc += ':{}'.format(parsed.port)

    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
