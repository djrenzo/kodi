import re
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import xbmcvfs
import plugintools

import textformat as tf

from queries import (
    query_programs, 
    query_seasons, 
    query_collections, 
    query_episodes,
    query_search,
    get_data_editorial_id,
    get_services,
    get_gbx_picky,
    get_hts,
    get_editorial_index,
    get_tab_contents,
    get_musica_items,
    get_channel_cards,
    get_channel_playback,
    extract_pagination_from_text,
    normalize_series_ref_id,
    PLAY_HEADERS,
    PLAY_HEADERS_RTVE,
    apiKeys,
    gen_play_headers,
    get_programdata,
    get_current_program
    )

THUMB_NEW = "https://m.media-amazon.com/images/I/71yx+aFpz1L.png"
AK = apiKeys()
img_links = {
    "telecinco": "https://i.scdn.co/image/ab6761610000e5ebc66c6848262ec04bc34a0dee",
    "cuatro": "https://cloudfront-eu-central-1.images.arcpublishing.com/prisaradio/TR35WHZ6XVLEDKA7GSUK4JUWQQ.jpg"
}

def _log(msg):
    plugintools.log(f"--> mediaset - {msg} <--")

def _download_context_menu(url="", extra="", ref_id="", title=""):
    return [(
        "Download",
        "RunPlugin(%s)" % plugintools.build_plugin_url(
            action="download_item", title=title, url=url, extra=extra, ref_id=ref_id
        )
    )]

def run():
    _log("Running")
    # plugintools.set_view(plugintools.LIST)

    # Get params
    params = plugintools.get_params()
    if not params.get("action"):
        main_list(params)

    else:
       action = params.get("action")
       url = params.get("url")
       exec(f"{action}(params)")
    plugintools.close_item_list()

def main_list(params):
    _log("Main List")
    # plugintools.set_view(plugintools.LIST)
    xbmc.executebuiltin('UpdateAddonRepos')

    # Search #
    plugintools.add_item(
        action="busca_mitele",
        title=tf.title("search"),
        thumbnail=THUMB_NEW,
        fanart="https://album.mediaset.es/eimg/2017/11/03/RDrSzFS5nu4Eyyq5gGEES2.jpg",
        url="https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2FautomaticIndex%2Fmtweb%3Furl%3Dwww%252Emitele%252Ees%252Fdocumentales%252F%26page%3D",
        plot="1",
        folder=True
    )

    # Canales Directo #
    plugintools.add_item(
        action="canales_pre",
        title=tf.title("mediaset live"),
        thumbnail="https://album.mediaset.es/file/10002/2017/11/21/mediaset_circular_500_nuevo_-2_4af9.png",
        fanart="https://www.mundoplus.tv/wp-content/uploads/2021/04/med_.jpg",
        url="https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2FautomaticIndex%2Fmtweb%3Furl%3Dwww%252Emitele%252Ees%252Fseries%252Donline%252F%26page%3D",
        plot="1",
        folder=True
    )
    
    # Programas #
    plugintools.add_item(
        action="programas_mitele",
        title=tf.title("programas"),
        thumbnail=THUMB_NEW,
        fanart="https://album.mediaset.es/eimg/2017/11/03/RDrSzFS5nu4Eyyq5gGEES2.jpg",
        url="22Z26bWQ2cEi3sNWOb2Ke8",
        extra='1',
        page="0",
        folder=True
    )

    # Series #
    plugintools.add_item(
        action="serie_mitele", 
        title=tf.title("series"),
        thumbnail=THUMB_NEW,
        fanart="https://album.mediaset.es/eimg/2017/11/03/RDrSzFS5nu4Eyyq5gGEES2.jpg",
        url="https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2FautomaticIndex%2Fmtweb%3Furl%3Dwww%252Emitele%252Ees%252Fseries%252Donline%252F%26page%3D",
        plot="1",
        folder=True
    )

    # Miniseries #
    plugintools.add_item(
        action="miniserie_mitele",
        title=tf.title("miniseries"),
        thumbnail=THUMB_NEW,
        fanart="https://album.mediaset.es/eimg/2017/11/03/RDrSzFS5nu4Eyyq5gGEES2.jpg",
        folder=True
    )

    # Telenovelas #
    plugintools.add_item(
        action="programas_mitele",
        title=tf.title("telenovelas"),
        thumbnail=THUMB_NEW,
        fanart="https://album.mediaset.es/eimg/2017/11/03/RDrSzFS5nu4Eyyq5gGEES2.jpg",
        url="2mZkbC1O13uZh7qb0E7mEp",
        extra='1',
        page="",
        folder=True
    )

    # Universo MTMAD #
    plugintools.add_item(
        action="programas_mitele" ,
        title=tf.title("universo mtmad"),
        thumbnail=THUMB_NEW,
        fanart="https://album.mediaset.es/eimg/2017/11/03/RDrSzFS5nu4Eyyq5gGEES2.jpg",
        url="2TNd0h39AaNNnScls1juiJ",
        extra='1',
        page="",
        folder=True
    )

    # Documentales #
    plugintools.add_item(
        action="peliculas_mitele",
        title=tf.title("documentales"),
        thumbnail=THUMB_NEW,
        fanart="https://album.mediaset.es/eimg/2017/11/03/RDrSzFS5nu4Eyyq5gGEES2.jpg",
        url="https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2FautomaticIndex%2Fmtweb%3Furl%3Dwww%252Emitele%252Ees%252Fdocumentales%252F%26page%3D",
        plot="1",
        folder=True
    )

    # Musica #
    plugintools.add_item(
        action="menu_musica_mitele",
        title=tf.title("musica"),
        thumbnail=THUMB_NEW,
        fanart="https://album.mediaset.es/eimg/2017/11/03/RDrSzFS5nu4Eyyq5gGEES2.jpg",
        url="https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2FautomaticIndex%2Fmtweb%3Furl%3Dwww%252Emitele%252Ees%252Fmusica%252F%26page%3D",
        plot="1",
        folder=True
    )

# DONE
def programas_mitele(params):
    plugintools.set_view(plugintools.LIST)
    code = params.get("url")
    page = params.get("page")
    page_number = params.get("extra")

    programs, pageInfo = query_programs(code, after=page, limit=10)

    for p in programs:
        cardLink = p.get("cardLink")
        ref_id = cardLink.get("referenceId")
        url = cardLink.get("value")
        title = p.get("cardTitle")
        text = p.get("cardText")
        foto = f'https://img-prod-api2.mediasetplay.mediaset.it/api/images/mse/v5/esp/{ref_id}/image_vertical/500/700?r='

        plugintools.add_item(
            action="serie_mitele_temporadas",
            title=tf.programs_title(title),
            url=url,
            ref_id=ref_id,
            thumbnail=foto,
            fanart=foto,
            folder=True
        )

    if pageInfo.get("hasNextPage"):
        page = pageInfo.get("endCursor")
        page_number = int(page_number) + 1    

        plugintools.add_item(
            action="programas_mitele",
            url=str(code),
            title=tf.nextPage(page_number),
            extra=str(page_number),
            page=str(page),
            folder=True
        )

# DONE
def peliculas_mitele(params):
    _log("peliculas_mitele")
    page_number = params.get("plot")
    url5 = params.get("url")

    cuerpo = get_editorial_index(url5, page=page_number, size=24)

    for item in cuerpo.get("editorialObjects", []):
        title = item.get("title")
        img = item.get("image", {})
        foto = img.get("src")
        link = "https://www.mitele.es" + img.get("href", "")

        plugintools.add_item(
            action="miniserie_mitele_reproducir",
            title=tf.programs_title(title),
            url=link,
            thumbnail=foto,
            fanart=foto,
            folder=False,
            isPlayable=True,
            context_menu=_download_context_menu(url=link, title=title)
        )

    pagination = cuerpo.get("pagination") or {}
    actual_page = pagination.get("actualPage")
    total_pages = pagination.get("totalPages")

    if actual_page and total_pages and actual_page < total_pages:
        next_page = str(int(page_number) + 1)

        plugintools.add_item(
            action="peliculas_mitele",
            url=url5,
            plot=next_page,
            title=tf.nextPage(next_page),
            thumbnail="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
            fanart="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
            folder=True
        )

# DONE
def canales_pre(params):
    channels = {"telecinco": "T5",
                "cuatro": "CT"}

    programdata = get_programdata()

    for ch, internal in channels.items():
        plugintools.add_item(
            action="miniserie_mitele_reproducir" ,
            title=tf.channel_title(f"{get_current_program(programdata, internal)} - {ch}"),
            extra=ch,
            url=f"https://www.mitele.es/directo/{ch}/",
            thumbnail=img_links.get(ch),
            fanart=img_links.get(ch),
            folder=False,
            isPlayable=True
        )

    plugintools.add_item(
        action="otro_reproducir" ,
        title=tf.channel_title("La 1"),
        extra="",
        url="https://rtvelivestream.rtve.es/rtvesec/la1/la1_main_dvr_720.m3u8",
        thumbnail="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Logo_La_1.svg/1950px-Logo_La_1.svg.png",
        fanart="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Logo_La_1.svg/1950px-Logo_La_1.svg.png",
        folder=False,
        isPlayable=True
    )

    plugintools.add_item(
        action="otro_reproducir" ,
        title=tf.channel_title("La 2"),
        extra="",
        url="https://rtvelivestream.rtve.es/rtvesec/la2/la2_main_dvr_720.m3u8",
        thumbnail="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Logo_La_2.svg/1900px-Logo_La_2.svg.png",
        fanart="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Logo_La_2.svg/1900px-Logo_La_2.svg.png",
        folder=False,
        isPlayable=True
    )

    # Canales Directo #
    plugintools.add_item(
        action="canales",
        title=tf.title("all channels"),
        thumbnail="https://album.mediaset.es/file/10002/2017/11/21/mediaset_circular_500_nuevo_-2_4af9.png",
        fanart="https://www.mundoplus.tv/wp-content/uploads/2021/04/med_.jpg",
        url="https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2FautomaticIndex%2Fmtweb%3Furl%3Dwww%252Emitele%252Ees%252Fseries%252Donline%252F%26page%3D",
        plot="1",
        folder=True
    )

# DONE
def canales(params):
    _log("canales")
    plugintools.set_view(plugintools.LIST)

    for card in get_channel_cards():
        url = 'https://www.mitele.es/directo/' + card["slug"] + '/'

        plugintools.add_item(
            action="miniserie_mitele_reproducir" ,
            title=tf.channel_title(card["title"]),
            extra=card["slug"],
            url=url,
            thumbnail=card["image"],
            fanart=card["image"],
            folder=False,
            isPlayable=True
            )

# DONE
def menu_musica_mitele(params):
    plugintools.set_view(plugintools.LIST)

    plugintools.add_item(
        action="musica_mitele_temporadas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]puro cuatro[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        thumbnail="https://album.mediaset.es//parrillas/2019/10/04/e3ceb5881a0a1fdaad01296d7554868d1570194115.jpg",
        fanart="https://album.mediaset.es/eimg/2017/11/03/RDrSzFS5nu4Eyyq5gGEES2.jpg",
        url="https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2Frelated%2Fmtweb%3Fid%3D111622",
        plot="1",
        folder=True
    )

    plugintools.add_item(
        action="musica_mitele_temporadas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]mira mi musica[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        thumbnail="https://album.mediaset.es//parrillas/2019/10/04/e3ceb5881a0a1fdaad01296d7554868d1570194115.jpg",
        fanart="https://album.mediaset.es/eimg/2017/11/03/RDrSzFS5nu4Eyyq5gGEES2.jpg",
        url="https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2Ftabs%2Fmtweb%3Furl%3Dwww%252Emitele%252Ees%252Fmusica%252Fmira%252Dmi%252Dmusica%252Fde%255Fcine%252F%26tabId%3D111781.0%26page%3D1%26size%3D100",
        plot="1",
        folder=True
    )

# DONE
def musica_mitele_temporadas(params):
    url = params.get("url")

    for item in get_musica_items(url):
        titulo = item.get("subtitle") or item.get("title")
        img = item.get("image", {})
        url4 = "https://www.mitele.es" + img.get("href", "")
        foto = img.get("src", "").replace(
            "https://album.mediaset.es/cimg/",
            "https://d25t5ibzu764hw.cloudfront.net/cimg/"
        )

        plugintools.add_item(
            action="miniserie_mitele_reproducir",
            title=tf.programs_title(titulo),
            url=url4,
            thumbnail=foto,
            fanart=foto,
            folder=False,
            isPlayable=True
        )

# DONE
def busca_mitele(params):
    dialog = xbmcgui.Dialog()

    text = dialog.input(
        '[B][LOWERCASE][CAPITALIZE][COLOR orange]buscar en mitele: ejemplo: [COLOR white]la que se avecina[/COLOR][/CAPITALIZE][/LOWERCASE][/B]',
        type=xbmcgui.INPUT_ALPHANUM
    )
    if not text:
        return

    for item in query_search(text):
        cardLink = item.get("cardLink") or {}
        ref_id = cardLink.get("referenceId")
        url = cardLink.get("value")
        title = item.get("cardTitle")
        foto = f'https://img-prod-api2.mediasetplay.mediaset.it/api/images/mse/v5/esp/{ref_id}/image_vertical/500/700?r='

        plugintools.add_item(
            action="serie_mitele_temporadas",
            title=tf.programs_title(title),
            url=url,
            ref_id=ref_id,
            thumbnail=foto,
            fanart=foto,
            folder=True
        )

# DONE
def serie_mitele(params):
    page_number = params.get("plot")
    url5 = params.get("url")

    cuerpo = get_editorial_index(url5, page=page_number, size=100)
    pagination = cuerpo.get('pagination') or {}
    pagina_actual = pagination.get('actualPage')
    pagina_total = pagination.get('totalPages')

    for item in cuerpo.get('editorialObjects', []):
        ref_id = normalize_series_ref_id(item.get("id"))
        title = item.get('title')
        datos = item.get('image') or {}
        foto = datos.get('src')
        url = "https://www.mediasetinfinity.es" + (datos.get('href') or "")

        plugintools.add_item(
            action="serie_mitele_temporadas",
            title=tf.programs_title(title),
            thumbnail=foto,
            fanart=foto,
            url=url,
            ref_id=ref_id,
            extra=ref_id,
            folder=True
        )

    if pagina_actual and pagina_total and pagina_actual < pagina_total:
        next_page = str(pagina_actual + 1)

        plugintools.add_item(
            action="serie_mitele",
            url=url5,
            plot=next_page,
            title=tf.nextPage(next_page),
            thumbnail="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
            fanart="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
            folder=True
        )

# DONE
def serie_mitele_temporadas(params):
    _log("Mitele Temporadas")
    thumbnail = params.get("thumbnail")
    serie_id = params.get("ref_id")

    for season in query_seasons(serie_id):
        cardLink = season.get("cardLink")
        url = cardLink.get("value")
        title = season.get("seasonTitle")
        season_id = cardLink.get("referenceId")

        plugintools.add_item(
            action="show_collections",
            title=tf.seasons_title(title),
            page='',
            extra= '1',
            url=url,
            ref_id=season_id,
            thumbnail=thumbnail,
            fanart=thumbnail,
            folder=True
        )

# DONE
def show_collections(params):
    plugintools.set_view(plugintools.LIST)
    _log("show_collections")
    url = params.get("url")
    thumbnail = params.get("thumbnail")
    season_id = params.get("ref_id")
    collections = query_collections(season_id)

    for c in collections:
        title = c.get("title")
        collection_id = c.get("id")

        plugintools.add_item(
            action="show_episodes",
            url=url,
            ref_id=collection_id,
            page="",
            title=tf.collections_title(title),
            extra="1",
            fanart=thumbnail,
            thumbnail=thumbnail,
            folder=True
        )

# DONE
def show_episodes(params):
    _log("show_episodes")
    url = params.get("url")
    page_number = params.get("extra")
    page = params.get("page")
    thumbnail = params.get("thumbnail")
    collection_id = params.get("ref_id")

    episodes, pageInfo = query_episodes(collection_id, after=page, limit=10)

    plugintools.set_view(plugintools.MOVIES, 503)

    for ep in episodes:
        cardLink = ep.get("cardLink")
        ref_id = cardLink.get("referenceId")
        url = cardLink.get("value")
        title = ep.get("cardTitle")
        description = ep.get("description") or ep.get("cardText") or ""
        img = ep.get("cardImages")[0]
        img_url = f"https://img-prod-api2.mediasetplay.mediaset.it/api/images/mp/v5/esp/{img.get('id')}/image_keyframe_poster/360/203?r={img.get('r')}"

        aired = (ep.get("lastPublishDate") or "")[:10]
        duration_seconds = ep.get("duration")
        rating = ep.get("cardEditorialMetadataRating")
        plot = tf.episodes_plot(
            description,
            aired=ep.get("cardEditorialMetadata"),
            duration=ep.get("durationString"),
            rating=rating
        )

        info_labels = {"Title": title, "Plot": plot}
        if aired:
            info_labels["Aired"] = aired
            info_labels["Premiered"] = aired
        if rating:
            info_labels["Mpaa"] = rating
        if duration_seconds:
            info_labels["Duration"] = duration_seconds

        plugintools.add_item(
            action="miniserie_mitele_reproducir" ,
            title=tf.episodes_title(title),
            plot=plot,
            info_labels=info_labels,
            url=url,
            ref_id=ref_id,
            thumbnail=img_url,
            fanart=thumbnail,
            folder=False,
            isPlayable=True,
            context_menu=_download_context_menu(url=url, ref_id=ref_id, title=title)
        )
    
    if pageInfo.get("hasNextPage"):
        page_number = int(page_number) + 1    

        plugintools.add_item(
            action="show_episodes",
            url=url,
            ref_id=collection_id,
            extra=str(page_number),
            page=pageInfo.get("endCursor"),
            title=tf.nextPage(page_number),
            fanart=thumbnail,
            thumbnail=thumbnail,
            folder=True
        ) 

# DONE
def miniserie_mitele(params):
    url_base = "https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2FautomaticIndex%2Fmtweb%3Furl%3Dwww%252Emitele%252Ees%252Fminiseries%252F%26page%3D"
    cuerpo = get_editorial_index(url_base, page="1", size=24)

    for item in cuerpo.get('editorialObjects', []):
        tabs = item.get('id') + '.0'
        name = item.get('title')
        datos = item.get('image') or {}
        foto = datos.get('src')
        url = "https://www.mitele.es" + (datos.get('href') or "")

        plugintools.add_item(
            action="miniserie_mitele_server",
            title=tf.programs_title(name),
            extra=tabs,
            url=url,
            thumbnail=foto,
            fanart=foto,
            folder=True
        )

def _add_miniserie_episode(node):
    title = node.get("title", "").replace("\\", "")
    subtitle = node.get("subtitle", "").replace("\\", "")
    synopsis = node.get("info", {}).get("synopsis", "").replace("\\", "")
    link = "https://www.mitele.es" + node.get("link", {}).get("href", "").replace("\\", "")
    thumbnail_url = node.get("images", {}).get("thumbnail", {}).get("src", "").replace("\\", "")

    plugintools.add_item(
        action="miniserie_mitele_reproducir",
        title=f"[B][COLOR white]{subtitle} [COLOR gold]{title}[/COLOR][/B]",
        url=link,
        plot=f"[B][COLOR gold]{synopsis}[/COLOR][/B]",
        thumbnail=thumbnail_url,
        fanart=thumbnail_url,
        folder=False,
        isPlayable=True,
        context_menu=_download_context_menu(url=link, title=f"{subtitle} {title}".strip())
    )

# DONE
def miniserie_mitele_server(params):
    plugintools.set_view(plugintools.MOVIES, 503)

    tag = params.get("extra")
    url3 = params.get("url")
    page = params.get("page", 1)
    thumbnail = params.get("thumbnail")

    data, response_text = get_tab_contents(url3, tag, page=page)
    if data is None:
        plugintools.log("Error: could not fetch or parse tab contents")
        return

    for content in data.get("contents", []):
        children = content.get("children", [])
        if children:
            for episode in children:
                _add_miniserie_episode(episode)
        else:
            title = content.get("title", "").replace("\\", "")
            if re.match(r"Temporada \d+", title):
                continue
            _add_miniserie_episode(content)

    pagination = extract_pagination_from_text(response_text)
    if pagination:
        current_page, total_pages = pagination

        if current_page < total_pages:
            next_page = current_page + 1

            plugintools.add_item(
                action="miniserie_mitele_server",
                title=tf.nextPage(next_page),
                extra=tag,
                url=url3,
                page=str(next_page),
                thumbnail=thumbnail,
                fanart=thumbnail,
                folder=True
            )

def _resolve_stream(params):
    """Resolve params (as passed to miniserie_mitele_reproducir/download_item) into the
    playable manifest URL, headers, subtitles and live flag, without playing/downloading it."""
    canal = params.get("extra")
    if canal:
        picky, bbx, gbx, subs = get_channel_playback(canal)

    else: ## NEW CODE ##
        programa = params.get("url")
        programa = programa.replace('mediasetinfinity.es','mitele.es')
        dataEditorialId = get_data_editorial_id(programa)
        services = get_services(dataEditorialId)
        gbx_temp, gbx, caronte, picky, bbx = get_gbx_picky(services)
        subs = caronte.get("subtitles")
        if subs:
            subs = [i.get("vtt") for i in subs]
    
    UID, UIDSignature, signatureTimestamp = AK.get_api_keys()

    payload = {
        "gid": UID,
        "time":signatureTimestamp,
        "sig": UIDSignature,
        "gbx": gbx,
        "bbx": bbx
        }

    try:
        hts = get_hts(payload)
    except Exception as e:
        raise ValueError(
            f"Error: {e},",
            f"{payload}"
        )

    # dls[0] is the FairPlay-DRM manifest; swap to the plain HLS variant Kodi can play.
    picky = picky.replace('hls-fairplay.ism', 'main.ism')

    return f"{picky}?{hts}", PLAY_HEADERS, subs, bool(canal)

# DONE
def miniserie_mitele_reproducir(params):
    content_id = plugintools.content_id_for(params.get("url"), params.get("ref_id"))
    local_video, local_subs = plugintools.find_downloaded_media(content_id)
    if local_video:
        _log(f"miniserie_mitele_reproducir: playing downloaded copy [{local_video}]")
        plugintools.play_local_file(local_video, subtitles=local_subs)
        return

    url, headers, subs, is_live = _resolve_stream(params)

    plugintools.play_resolved_url(
            url=url,
            subtitles=subs,
            headers=headers,
            is_live=is_live
        )

def download_item(params):
    _log("download_item")
    title = params.get("title") or "video"

    try:
        url, headers, subs, is_live = _resolve_stream(params)
    except Exception as e:
        _log(f"download_item: could not resolve stream: {e}")
        xbmcgui.Dialog().notification("Mediaset", "No se pudo resolver el video para descargar", xbmcgui.NOTIFICATION_ERROR)
        return

    content_id = plugintools.content_id_for(params.get("url"), params.get("ref_id"))
    plugintools.download_hls_stream(url, title, content_id, headers=headers, subtitles=subs, is_live=is_live)

# DONE
def otro_reproducir(params):
    url = params.get("url")

    plugintools.play_resolved_url(
            url=url, 
            # subtitles=subs,
            headers=PLAY_HEADERS_RTVE
        )

run()