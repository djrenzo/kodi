import os
import requests
import json
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
    get_data_editorial_id,
    get_services,
    get_gbx_picky,
    get_hts,
    HEADER2,
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
    plugintools.log(f"--> miteledidi - {msg} <--")

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

## TODO ##
def peliculas_mitele(params):
    numero = params.get("plot")
    url5 = params.get("url")
    url = url5 + numero + "%26id%3Da-z%26size%3D24"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
        "Upgrade-Insecure-Requests": "1"}

    url = requests.get(url, headers=headers).text

    page = plugintools.find_single_match(url,'totalPages":(.*?),"elementsPerPage"')
    matches = plugintools.find_multiple_matches(url,'id":".*?","title":".*?".*?src":".*?".*?"href":".*?".*?')

    for generos in matches:
        url = "https://www.mitele.es" + plugintools.find_single_match(generos,'href":"(.*?)"').replace('\\','')
        titulo = plugintools.find_single_match(generos,'title":"(.*?)"').replace('\\u00ed','i').replace('\\u00eda','e').replace('\\u00fa','u').replace('\\u00f3','o').replace('\\u00c1','a').replace('\\u00e9','e').replace('\\u00e1','a').replace('\\u00c9','e').replace('\\u00c9','e').replace('\\u0027',"'")
        foto = plugintools.find_single_match(generos,'src":"(.*?)".*?').replace('\\','')

        plugintools.add_item(
            action="miniserie_mitele_reproducir",
            title="[B][LOWERCASE][CAPITALIZE][COLOR gold][COLOR white] " + titulo + "[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
            url=url,
            thumbnail=foto,
            fanart=foto,
            folder=False,
            isPlayable=True
        )
    
    if page > numero :
        s = 'sumar'
        def dec(s):
            a = int("1")
            b = int(numero)
            suma = a + b
            return (str(suma))
        esto = dec(s)


        plugintools.add_item(
            action="peliculas_mitele",
            url=url5,
            plot=esto,
            title="[B][LOWERCASE][CAPITALIZE][COLOR lime]ir a la pagina siguiente[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
            thumbnail="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
            fanart="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
            folder=True
        )

## DONE ##
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

## TODO ##
def canales(params):
    plugintools.set_view(plugintools.LIST)
    url = 'https://www.mediasetinfinity.es/'
    thumbnail = params.get("thumbnail")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
        "Upgrade-Insecure-Requests": "1"}
    
    url3 = requests.get(url,headers=headers).text
    matches1 = plugintools.find_multiple_matches(url3,'md:pt-0 md:text-label-2">En directo</span>.*?1x, https://.*?".*?<img alt=".*?".*?class="w-full" href="/directo/.*?/.*?')
    
    for generas in matches1:
        canal = plugintools.find_single_match(generas,'href="/directo/(.*?)/.*?')
        titulo = plugintools.find_single_match(generas,'<img alt="(.*?)".*?')

        if not 'Acontra' in titulo and not 'Fight Sports' in titulo:
            url = 'https://www.mitele.es/directo/' + canal + '/'
            foto = plugintools.find_single_match(generas,'1x, (https://.*?)".*?')

            plugintools.add_item(
                action="miniserie_mitele_reproducir" ,
                title="[B][LOWERCASE][CAPITALIZE][COLOR gold][COLOR white] " + titulo + " [/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
                extra=canal,
                url=url,
                thumbnail=foto,
                fanart=foto,
                folder=False,
                isPlayable=True
            )

## TODO ##
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

## TODO ##
def musica_mitele_temporadas(params):
    url = params.get("url")
    thumbnail = params.get("thumbnail")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
        "Upgrade-Insecure-Requests": "1"
    }
    
    url3 = requests.get(url,headers=headers).text

    matches1 = plugintools.find_multiple_matches(url3,'{"id":".*?","title":".*?","subtitle":".*?landscape","src":".*?","alt":".*?duration.*?","href":".*?","target":"_self"')
    
    for generas in matches1:
        url4 = "https://www.mitele.es"+plugintools.find_single_match(generas,'duration.*?href":"(.*?)"').replace('\\','')
        titulo = plugintools.find_single_match(generas,'"subtitle":"(.*?)"')
        titulo2 = plugintools.find_single_match(generas,'self","title":"(.*?)"')
        foto = 'https://d25t5ibzu764hw.cloudfront.net/cimg/'+plugintools.find_single_match(generas,'"src":"https:....album.mediaset.es..cimg..(.*?)"').replace('\\','')
        
        plugintools.add_item(
            action="miniserie_mitele_reproducir",
            title="[B][LOWERCASE][CAPITALIZE][COLOR gold][COLOR white] " + titulo + " [/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
            url=url4,
            thumbnail=foto,
            fanart=foto,
            folder=False,
            isPlayable=True
        )

## TODO ##
def busca_mitele(params):
    numero = params.get("plot")
    dialog = xbmcgui.Dialog()

    d = dialog.input(
        '[B][LOWERCASE][CAPITALIZE][COLOR orange]buscar en mitele: ejemplo: [COLOR white]la que se avecina[/COLOR][/CAPITALIZE][/LOWERCASE][/B]',
        type=xbmcgui.INPUT_ALPHANUM
    )

    #url5= "https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2Fsearch%2Fmtweb%3Furl%3Dwww%252Emitele%252Ees%26text%3D"+d+"%26page%3D"+numero+"%26size%3D24%26type%3D"
    url5='https://ottesp.api-graph.mediaset.it/?extensions={"persistedQuery":{"version":1,"sha256Hash":"819f5ee79c4b589ce25bacbf2390d181311495e647bfff092a487b4e00552072"}}&variables={"first":10,"property":"search","query":"'+d+'","uxReference":"filteredSearch"}'
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0","x-m-user-context": "iw+AeyJsb2dnZWQiOnRydWUsInBsYXRmb3JtIjoid2ViIn0D","x-m-app-version": "1.0.20","x-m-platform": "WEB","x-m-property": "MITELE"}

    url = requests.get(url5,headers=headers).text

    matches = plugintools.find_multiple_matches(url,'cardLink":{"behavior":"bookmark","referenceId":".*?".*?"value":".*?".*?"cardTitle":".*?".*?')

    for generos in matches:
        patron = plugintools.find_single_match(generos,'cardLink":{"behavior":"bookmark","referenceId":"(.*?)".*?"value":"(.*?)".*?"cardTitle":"(.*?)".*?')
        titulo = patron[2]
        url = patron[1] 
        ids = patron[0]
    
        foto = 'https://img-prod-api2.mediasetplay.mediaset.it/api/images/mse/v5/esp/'+ids+'/image_vertical/500/700?r='

        plugintools.add_item(
            action="serie_mitele_temporadas",
            title="[B][LOWERCASE][CAPITALIZE][COLOR gold][COLOR white] " + titulo + "[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
            url=url,
            thumbnail=foto,
            fanart=foto,
            folder=True
        )

## TODO ##
def serie_mitele(params):
    numero = params.get("plot")
    url5 = params.get("url")
    url = url5 + numero + "%26id%3Da-z%26size%3D100"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0"
    }

    cuerpo = requests.get(url,headers=headers).json()
    group = cuerpo.get('editorialObjects')

    try:
        pagina = cuerpo.get('pagination')
        pagina_actual = pagina.get('actualPage')
        pagina_total = pagina.get('totalPages')

    except:
        pass

    for item in group:
        ref_id = item.get("id")

        if len(ref_id) == 6:
            prefix = "MS000000"
        elif len(ref_id) == 7:
            prefix = "MS00000"
        ref_id = f"{prefix}{ref_id}"

        title = item.get('title')
        datos = item.get('image')
        foto = datos.get('src')
        url = "https://www.mediasetinfinity.es" + datos.get('href')

        plugintools.add_item(
            action="serie_mitele_temporadas",
            title="[B][LOWERCASE][CAPITALIZE][COLOR gold][COLOR white] " + str(title) + "[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
            thumbnail=str(foto),
            fanart = str(foto),
            url=str(url),
            ref_id=ref_id,
            extra=ref_id,
            folder=True
        )

    try:
        if pagina_actual == pagina_total:
            pass

        else:
            a = int("1")
            b = int(pagina_actual)
            suma = a+b
            esto =  (str(suma))

            plugintools.add_item(
                action="serie_mitele",
                url=url5,
                plot=esto,
                title="[B][LOWERCASE][CAPITALIZE][COLOR lime]ir a la pagina siguiente[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
                thumbnail="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
                fanart="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
                folder=True
            )
    
    except:
        pass

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

    for ep in episodes:
        cardLink = ep.get("cardLink")
        ref_id = cardLink.get("referenceId")
        url = cardLink.get("value")
        title = ep.get("cardTitle")
        plot = ep.get("description")
        img = ep.get("cardImages")[0]
        img_url = f"https://img-prod-api2.mediasetplay.mediaset.it/api/images/mp/v5/esp/{img.get('id')}/image_keyframe_poster/360/203?r={img.get('r')}"

        plugintools.set_view(plugintools.MOVIES,503)

        plugintools.add_item(
            action="miniserie_mitele_reproducir" ,
            title=tf.episodes_title(title),
            plot=tf.episodes_plot(plot),
            url=url,
            ref_id=ref_id,
            thumbnail=img_url,
            fanart=thumbnail,
            folder=False,
            isPlayable=True
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

## TODO ##
def miniserie_mitele(params):
    url = "https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=%2FautomaticIndex%2Fmtweb%3Furl%3Dwww%252Emitele%252Ees%252Fminiseries%252F%26page%3D1%26id%3Da-z%26size%3D24"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
        "Upgrade-Insecure-Requests": "1"
        }

    cuerpo = requests.get(url, headers=headers).json()
    group = cuerpo.get('editorialObjects')

    try:
        pagina = cuerpo.get('pagination')
        pagina_actual = pagina.get('actualPage')
        pagina_total = pagina.get('totalPages')

    except:
        pass

    for item in group:
        tabs = item.get('id') + '.0'
        name = item.get('title')
        datos = item.get('image')
        foto = datos.get('src')
        url = "https://www.mitele.es" + datos.get('href')

        plugintools.add_item(
            action="miniserie_mitele_server",
            title="[B][LOWERCASE][CAPITALIZE][COLOR gold][COLOR white] " + name + "[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
            extra=tabs,
            url=url,
            thumbnail=foto,
            fanart=foto,
            folder=True
        )

## TODO ##
def miniserie_mitele_server(params):
    plugintools.set_view(plugintools.MOVIES, 503)

    tag = params.get("extra")
    url3 = params.get("url")
    page = params.get("page", 1)
    thumbnail = params.get("thumbnail")

    # Construir la URL
    url = (
        f"https://mab.mediaset.es/1.0.0/get?oid=bitban&eid=/tabs/mtweb?"
        f"url={url3}%26tabId={tag}%26page%3D{page}%26size%3D50"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0",
        "Accept": "application/json",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
        "Upgrade-Insecure-Requests": "1"
    }

    # Solicitar datos a la API
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        plugintools.log(f"Error: {response.status_code}")
        return

    # Parsear la respuesta como JSON
    try:
        data = response.json()
    except json.JSONDecodeError:
        plugintools.log("Error: La respuesta no es un JSON valido.")
        return

    # Procesar los contenidos
    contents = data.get("contents", [])
    for content in contents:
        children = content.get("children", [])
        if children:
            for episode in children:
                title = episode.get("title", "").replace("\\", "")
                subtitle = episode.get("subtitle", "").replace("\\", "")
                synopsis = episode.get("info", {}).get("synopsis", "").replace("\\", "")
                link = "https://www.mitele.es" + episode.get("link", {}).get("href", "").replace("\\", "")
                thumbnail_url = episode.get("images", {}).get("thumbnail", {}).get("src", "").replace("\\", "")
                plugintools.set_view(plugintools.MOVIES, 503)

                plugintools.add_item(
                    action="miniserie_mitele_reproducir",
                    title=f"[B][COLOR white]{subtitle} [COLOR gold]{title}[/COLOR][/B]",
                    url=link,
                    plot=f"[B][COLOR gold]{synopsis}[/COLOR][/B]",
                    thumbnail=thumbnail_url,
                    fanart=thumbnail_url,
                    folder=False,
                    isPlayable=True
                )
        else:
            title = content.get("title", "").replace("\\", "")
            subtitle = content.get("subtitle", "").replace("\\", "")
            synopsis = content.get("info", {}).get("synopsis", "").replace("\\", "")
            link = "https://www.mitele.es" + content.get("link", {}).get("href", "").replace("\\", "")
            thumbnail_url = content.get("images", {}).get("thumbnail", {}).get("src", "").replace("\\", "")

            if re.match(r"Temporada \d+", title):
                pass

            else:
                plugintools.set_view(plugintools.MOVIES, 503)
                plugintools.add_item(
                    action="miniserie_mitele_reproducir",
                    title=f"[B][COLOR white]{subtitle} [COLOR gold]{title}[/COLOR][/B]",
                    url=link,
                    plot=f"[B][COLOR gold]{synopsis}[/COLOR][/B]",
                    thumbnail=thumbnail_url,
                    fanart=thumbnail_url,
                    folder=False,
                    isPlayable=True
                )
    try:
        data = response.text
        matches = re.findall(r'"actualPage":(\d+),"totalPages":(\d+)', data)

        if matches: # Si encontramos una coincidencia
            current_page = int(matches[0][0])  # El valor de actualPage
            total_pages = int(matches[0][1])

            plugintools.log(f"Current page: {current_page}, Total pages: {total_pages}")  # Log de las pa­ginas

            if current_page < total_pages:

                plugintools.add_item(
                    action="",
                    title=f"[B][COLOR orange]pagina: {current_page}, paginas totales: {total_pages}[/COLOR][/B]",
                    folder=False
                )

                next_page = current_page + 1
                plugintools.log(f"Adding next page: {next_page}")

                plugintools.add_item(
                    action="miniserie_mitele_server",
                    title="[B][COLOR lime]Capitulos siguientes >>[/COLOR][/B]",
                    extra=tag,
                    url=url3,
                    page=str(next_page),
                    thumbnail=thumbnail,
                    fanart=thumbnail,
                    folder=True
                )

    except:
        pass

# DONE
def miniserie_mitele_reproducir(params):
    canal = params.get("extra")
    if canal:
        resp = requests.get(f"https://caronte.mediaset.es/delivery/channel/mmc/{canal}/mtweb", headers=HEADER2).json()
        picky = resp.get("dls")[0].get("stream")
        # picky = [s for s in resp.get("dls") if s.get("quality") == "hd"][-1].get("stream")
        bbx = resp.get("bbx")
        gbx = requests.get("https://mab.mediaset.es/1.0.0/get?oid=mtmw&eid=/api/mtmw/v3/gbx/mtweb/" + canal, headers=HEADER2).json().get("gbx")
        subs = resp.get("subtitles")

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

    plugintools.play_resolved_url(
            url=f"{picky}?{hts}",
            subtitles=subs,
            headers=PLAY_HEADERS
        )

# DONE
def otro_reproducir(params):
    url = params.get("url")

    plugintools.play_resolved_url(
            url=url, 
            # subtitles=subs,
            headers=PLAY_HEADERS_RTVE
        )

run()