import os
import sys
 
# import urllib
# from urllib.parse import urlparse, urlencode
# from urllib.request import urlopen, Request
# from urllib.error import HTTPError
# import inputstreamhelper
import re
import requests
import xbmc
import xbmcvfs
import xbmcgui
import xbmcaddon
import xbmcplugin
import plugintools
import unicodedata
import base64
import requests
import shutil
import base64
import time
import random
import six
 
addon = xbmcaddon.Addon()
icon = addon.getAddonInfo('icon')
myaddon = xbmcaddon.Addon("plugin.video.atresplayerdidi")
Set_Color = myaddon.getSetting('SetColor')
Set_View = myaddon.getSetting('SetView')

def run():
    plugintools.set_view(plugintools.LIST)
    params = plugintools.get_params()

    if params.get("action") is None:
        main_list(params)

    else:
       action = params.get("action")
       url = params.get("url")
       exec(action + "(params)")

    plugintools.close_item_list()

def main_list(params): 
    plugintools.set_view(plugintools.LIST)
    xbmc.executebuiltin('UpdateAddonRepos')
  
    plugintools.add_item(
        action="buscador",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]buscador[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    )  
    
    plugintools.add_item(
        action="sietedias",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]ultimos 7 dias[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/page/u7d/5a6b32667ed1a834493ec03b',
        thumbnail="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2020/10/08/5AF1F499-F837-4BBA-A0B2-75BFEF221B13//720x540.jpg",
        fanart="https://www.larazon.es/resizer/Obu0kOz7we-Z6QtDTC347TPFj0k=/840x0/smart/filters:format(jpg)/cloudfront-eu-central-1.images.arcpublishing.com/larazon/2HTMHMGCVFFFDKUF2WMUPFRAW4.jpg",
        folder=True
    ) 

    plugintools.add_item(
        action="tv_atresmedia",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white] tv de atresmedia en directo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/live',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    ) 

    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]originales vix[COLOR lime] nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/678e611c73e8690007b9d824?size=100&page=',
        page='0',
        thumbnail="https://www.vemostv.com/fotos/galerias/13962/13962_xxl_1.jpg",
        fanart="https://areajugones.sport.es/wp-content/uploads/2025/02/vix-en-atresplayer.jpg",
        folder=True
    )

    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white] Estrenos exclusivos en ViX[COLOR lime] nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/5c4095d67ed1a880faf098cd?size=100&page=',
        page='0',
        thumbnail="https://www.vemostv.com/fotos/galerias/13962/13962_xxl_1.jpg",
        fanart="https://areajugones.sport.es/wp-content/uploads/2025/02/vix-en-atresplayer.jpg",
        folder=True
    )

    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]añadido recientemente[COLOR lime] nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/5b6ae2b97ed1a8bbd1275c22?size=100&page=',
        page='0',
        thumbnail="https://www.vemostv.com/fotos/galerias/13962/13962_xxl_1.jpg",
        fanart="https://areajugones.sport.es/wp-content/uploads/2025/02/vix-en-atresplayer.jpg",
        folder=True
    )
    
    plugintools.add_item(
        action="programas",
        title = "[B][LOWERCASE][CAPITALIZE][COLOR white]preestrenos[COLOR lime]nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/66e03e1463a63b0007d94c09?size=100&page=',
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    ) 

    plugintools.add_item(
        action="programas",
        title = "[B][LOWERCASE][CAPITALIZE][COLOR white]clasicos atresplayer[COLOR lime]nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/632245ec7141b0e419991186?size=100&page=',
        page='0',
        thumbnail="https://www.vemostv.com/fotos/galerias/13962/13962_xxl_1.jpg",
        fanart="https://areajugones.sport.es/wp-content/uploads/2025/02/vix-en-atresplayer.jpg",
        folder=True
    )

    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]programas[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/search?entityType=ATPFormat&sectionCategory=true&mainChannelId=5a6b32667ed1a834493ec03b&categoryId=5a6a1ba0986b281d18a512b9&sortType=AZ&size=100&page=',
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    ) 

    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]series[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/search?entityType=ATPFormat&sectionCategory=true&mainChannelId=5a6b32667ed1a834493ec03b&categoryId=5a6a1b22986b281d18a512b8&sortType=AZ&size=100&page=',
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    )    

    plugintools.add_item(
        action="menu_cine",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]cine[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/search?entityType=ATPRecording&categoryId=5b5f2f777ed1a86860102144&size=8&page=0',
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    )  

    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]informativos[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/search?entityType=ATPFormat&sectionCategory=true&mainChannelId=5a6b32667ed1a834493ec03b&categoryId=5a6a215e986b281d18a512bc&sortType=THE_MOST&size=8&page=',
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    )   

    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]vix telenovelas[COLOR lime]nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/5b1676d17ed1a87acd06c2fa?size=100&page=',
        page='0',
        thumbnail="https://www.vemostv.com/fotos/galerias/13962/13962_xxl_1.jpg",
        fanart="https://areajugones.sport.es/wp-content/uploads/2025/02/vix-en-atresplayer.jpg",
        folder=True
    )
    
    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]telenovelas atresplayer[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/search?entityType=ATPFormat&sectionCategory=true&mainChannelId=5a6b32667ed1a834493ec03b&categoryId=5a6a2313986b281d18a512be&sortType=AZ&size=100&page=',
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    )     

    plugintools.add_item(
        action ="novelas_nova",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]telenovelas nova[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/5b150ca67ed1a864fe8264ab?size=16&page=',
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    ) 

    plugintools.add_item(
        action="kidz",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white][COLOR fuchsia]kidz[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='',
        thumbnail="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2020/10/08/5AF1F499-F837-4BBA-A0B2-75BFEF221B13//720x540.jpg",
        fanart="https://www.larazon.es/resizer/Obu0kOz7we-Z6QtDTC347TPFj0k=/840x0/smart/filters:format(jpg)/cloudfront-eu-central-1.images.arcpublishing.com/larazon/2HTMHMGCVFFFDKUF2WMUPFRAW4.jpg",
        folder=True
    ) 
    
    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]infantil[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/search?entityType=ATPFormat&sectionCategory=true&mainChannelId=5a6b32667ed1a834493ec03b&categoryId=5a6a24b1986b281d18a512c0&sortType=AZ&size=100&page=',
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    )   

    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white]documentales[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/search?entityType=ATPFormat&sectionCategory=true&mainChannelId=5a6b32667ed1a834493ec03b&categoryId=5b067bf3986b28b0a27c2f42&sortType=THE_MOST&size=100&page=',
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    )

def sietedias(params):
    plugintools.set_view(plugintools.MOVIES,502) 
 
    url = params.get("url")
    thumbnail = params.get("thumbnail")
    request_headers = []
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body, response_headers = plugintools.read_body_and_headers(url, headers=request_headers)
    
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'{"id":".*?","type":".*?".*?"title":".*?,"href":".*?"}')

    for generos in matches: 
        url = plugintools.find_single_match(generos,'href":"(.*?)"')
        titulo = plugintools.find_single_match(generos,'"title":"(.*?)"')
 
        plugintools.add_item(
            action="cine_peliculas",
            title="[B][LOWERCASE][CAPITALIZE][COLOR white]ultimos 7 dias en " + titulo + "[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
            thumbnail=thumbnail,
            fanart =thumbnail,
            url=url+'?size=100&page=',
            page='0',
            folder=True
        )     

def cine_peliculas(params):
    plugintools.set_view(plugintools.MOVIES,502) 
    numero = params.get("page")
    url = params.get("url") + numero
    thumbnail = params.get("thumbnail")
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body, response_headers = plugintools.read_body_and_headers(url, headers=request_headers)
    url = body.strip().decode('utf-8')

    matches = plugintools.find_multiple_matches(url,'{"title":".*?".*?pathHorizontal":".*?".*?url":".*?startTime')

    for generos in matches: 
        url = 'https://api.atresplayer.com/player/v1/recording/'+plugintools.find_single_match(generos,'"contentId":"(.*?)"')
        titulo = plugintools.find_single_match(generos,'"title":"(.*?)"')
        foto = plugintools.find_single_match(generos,'pathHorizontal":"(.*?)".*?')+'/1280x720.jpg'
        s='sumar'
        def dec(s):
            a = int("1")
            b = int(numero)
            suma = a+b
            return (str(suma))
        esto = dec(s) 

        plugintools.add_item(
            action="cine_peliculas2",
            title ="[B][LOWERCASE][CAPITALIZE][COLOR white]"+titulo+"[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
            thumbnail=foto,
            fanart=foto,
            url=url,
            folder=False,
            isPlayable=True
        )   
 
    #plugintools.add_item(action = "cine_peliculas" , title ="[B][LOWERCASE][CAPITALIZE][COLOR lime]pagina siguiente "+str(esto)+"[/B][/COLOR][/CAPITALIZE][/LOWERCASE]", thumbnail = "https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",fanart = "https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png", url =params.get("url"),page=esto ,folder=True ) 

def cine_peliculas2(params):
    plugintools.log("atresplayer.capitulo2 "+repr(params))    
    thumbnail = params.get("thumbnail")    
    url = 'https://pastebin.com/raw/Th0mgdXX'
    
    headers= {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0"}
    url = requests.get(url,headers=headers,verify=False,timeout=5)
    url = url.text

    cookies1 = plugintools.find_single_match(url,'"(.*?)"')
    url = 'https://pastebin.com/raw/kCKm22hH'

    headers= {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0"}
    url = requests.get(url, headers=headers, verify=False, timeout=5)
 
    url = url.text

    cookies2 = plugintools.find_single_match(url,'"(.*?)"')

    headers1 = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
        "Accept": "*/*",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3","referer":"https://www.atresplayer.com/documentales/pongamos-que-hablo-de-sabina/temporada-1/capitulo-1-los-pecados_5ebbdbbd7ed1a8354e4201d3/","cookie":cookies1}
    
    headers2 = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
        "Accept": "*/*",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3","referer":"https://www.atresplayer.com/documentales/pongamos-que-hablo-de-sabina/temporada-1/capitulo-1-los-pecados_5ebbdbbd7ed1a8354e4201d3/","cookie":cookies2}
    
    viva = {"http": "http://14.139.189.213:3128"}

    esto = requests.get(params.get("url"), proxies=viva, headers=headers1).text

    if 'm3u8' in esto:
        esto = requests.get(params.get("url"), proxies=viva, headers=headers1).text

    else:
        esto = requests.get(params.get("url"),proxies=viva, headers=headers2).text
    
    url = plugintools.find_single_match(esto,'src":"(.*?m3u8.*?)".*?').replace('drm','')+'|user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36'
    plugintools.play_resolved_url(url)

def menu_cine(params): 
    plugintools.set_view(plugintools.LIST)   
    plugintools.add_item(
        action="cine_peliculas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white] cine los ultimos 7 dias[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/search?entityType=ATPRecording&categoryId=5b5f2f777ed1a86860102144&size=50&page=',
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    )  
    
    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white] cine todas las peliculas[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/search?entityType=ATPFormat&sectionCategory=true&mainChannelId=5a6b32667ed1a834493ec03b&categoryId=5b5f2f777ed1a86860102144&sortType=THE_MOST&size=50&page=',
        page='0',
        thumbnail="https://i0.wp.com/www.audiovisual451.com/wp-content/uploads/Atresplayer.jpeg?fit=300%2C236&ssl=1",
        fanart="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2018/01/24/3A62BD1C-A059-40B1-8688-8BECED7D41A7/1280x720.jpg",
        folder=True
    )     

def novelas_nova(params):   
    plugintools.set_view(plugintools.LIST)   
    
    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white] telenovelas nova[COLOR lime]portada[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/5b150ca67ed1a864fe8264ab?size=16&page=',
        page='0',
        thumbnail="https://pbs.twimg.com/media/FKgp4sNWQAIeB4f.jpg",
        fanart="https://pbs.twimg.com/media/FKgp4sNWQAIeB4f.jpg",
        folder=True
    ) 

    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white] telenovelas nova[COLOR lime]  destacadas[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/5db3f6437ed1a8f9e42fe980?size=50&page=',
        page='0',
        thumbnail="https://pbs.twimg.com/media/FKgp4sNWQAIeB4f.jpg",
        fanart="https://pbs.twimg.com/media/FKgp4sNWQAIeB4f.jpg",
        folder=True
    ) 

    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white] telenovelas nova[COLOR lime]Lo mejor de Turquía[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/5baa09227ed1a8d2fcc378d2?size=50&page=',
        page='0',
        thumbnail="https://pbs.twimg.com/media/FKgp4sNWQAIeB4f.jpg",
        fanart="https://pbs.twimg.com/media/FKgp4sNWQAIeB4f.jpg",
        folder=True
    ) 

    plugintools.add_item(
        action="programas",
        title="[B][LOWERCASE][CAPITALIZE][COLOR white] telenovelas nova[COLOR lime]añadidas recientemente[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
        url='https://api.atresplayer.com/client/v1/row/5b6ae2b97ed1a8bbd1275c22?size=50&page=',
        page='0',
        thumbnail="https://pbs.twimg.com/media/FKgp4sNWQAIeB4f.jpg",
        fanart="https://pbs.twimg.com/media/FKgp4sNWQAIeB4f.jpg",
        folder=True
    ) 

def tv_atresmedia(params):
    plugintools.set_view(plugintools.MOVIES,502)

    url = params.get("url")
    thumbnail = params.get("thumbnail")
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body, response_headers = plugintools.read_body_and_headers(url, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'(?s)"image":{"title":".*?".*?"url":"/directos/.*?/","href":".*?".*?contentId":".*?".*?logoURL":".*?"')
    
    for generos in matches: 
        patron = plugintools.find_single_match(generos,'(?s)"image":{"title":"(.*?)".*?"url":"/directos/(.*?)/","href":".*?".*?contentId":"(.*?)".*?logoURL":"(.*?)"')
        emision = patron[0]
        emision = emision.replace("Sección 2023", "").replace("Sección", "").replace("(", "").replace(")", "")
        url = 'https://api.atresplayer.com/player/v1/live/'+patron[2]+'?NODRM=true'
        canal = patron[1]
        foto = patron[3]

        plugintools.add_item(
            action="playdirect",
            title="[B][LOWERCASE][CAPITALIZE][COLOR white]"+canal+"[COLOR yellow] '"+emision+"'[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
            thumbnail=foto,
            fanart=foto,
            url=url,
            folder=False,
            isPlayable=True
        )     

def playdirect(params): 
    url = params.get("url")
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    if six.PY3==True:
        url = body.strip().decode('utf-8')

    url = plugintools.find_single_match(url,'"sourcesLive":.{"src":"(.*?)"')           
    url = url+'|user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36'
    
    plugintools.play_resolved_url(url) 

def kidz(params):  
    plugintools.set_view(plugintools.LIST) 
    thumbnail = params.get("thumbnail")    

    plugintools.add_item(action = "" , title = "[B][LOWERCASE][CAPITALIZE][COLOR yellow]-------[COLOR aqua] kidz[COLOR yellow]-------[/CAPITALIZE][/LOWERCASE][/B][/COLOR]", thumbnail =thumbnail, fanart =thumbnail,  folder = False )  
    
    plugintools.add_item(action = "programas" , title = "[B][LOWERCASE][CAPITALIZE][COLOR white] [COLOR fuchsia]kidz [COLOR white] destacados [COLOR lime] nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",url='https://api.atresplayer.com/client/v1/row/5bf67e2f7ed1a8c62d08a2d0?size=100&page=',page='0', thumbnail ="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2020/10/08/5AF1F499-F837-4BBA-A0B2-75BFEF221B13//720x540.jpg", fanart = "https://www.larazon.es/resizer/Obu0kOz7we-Z6QtDTC347TPFj0k=/840x0/smart/filters:format(jpg)/cloudfront-eu-central-1.images.arcpublishing.com/larazon/2HTMHMGCVFFFDKUF2WMUPFRAW4.jpg",  folder = True )
    
    plugintools.add_item(action = "programas" , title = "[B][LOWERCASE][CAPITALIZE][COLOR white] [COLOR fuchsia]kidz [COLOR white] universo kidz [COLOR lime] nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",url='https://api.atresplayer.com/client/v1/row/5bc73fa67ed1a82a8faf01af?size=100&page=',page='0', thumbnail ="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2020/10/08/5AF1F499-F837-4BBA-A0B2-75BFEF221B13//720x540.jpg", fanart = "https://www.larazon.es/resizer/Obu0kOz7we-Z6QtDTC347TPFj0k=/840x0/smart/filters:format(jpg)/cloudfront-eu-central-1.images.arcpublishing.com/larazon/2HTMHMGCVFFFDKUF2WMUPFRAW4.jpg",  folder = True ) 

    plugintools.add_item(action = "programas" , title = "[B][LOWERCASE][CAPITALIZE][COLOR white] [COLOR fuchsia]kidz [COLOR white] recomendados para ti [COLOR lime] nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",url='https://api.atresplayer.com/client/v1/row/recommended?context=canal&contextValue=5f69bd317ed1a83f0b8eadf0&channelId=5f69bd317ed1a83f0b8eadf0&contentType=ATPFormat&vb=v2&v=v2&app=false&connection=wifi&visitorId=0c75d51f8b4&marketingId=51564742100308858432420602973194195686&os=Windows%2010&size=100&page=',page='0', thumbnail ="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2020/10/08/5AF1F499-F837-4BBA-A0B2-75BFEF221B13//720x540.jpg", fanart = "https://www.larazon.es/resizer/Obu0kOz7we-Z6QtDTC347TPFj0k=/840x0/smart/filters:format(jpg)/cloudfront-eu-central-1.images.arcpublishing.com/larazon/2HTMHMGCVFFFDKUF2WMUPFRAW4.jpg",  folder = True ) 

    plugintools.add_item(action = "programas" , title = "[B][LOWERCASE][CAPITALIZE][COLOR white] [COLOR fuchsia]kidz [COLOR white] para ver en familia [COLOR lime] nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",url='https://api.atresplayer.com/client/v1/row/5bcf05017ed1a8138977c1c1?size=100&page=',page='0', thumbnail ="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2020/10/08/5AF1F499-F837-4BBA-A0B2-75BFEF221B13//720x540.jpg", fanart = "https://www.larazon.es/resizer/Obu0kOz7we-Z6QtDTC347TPFj0k=/840x0/smart/filters:format(jpg)/cloudfront-eu-central-1.images.arcpublishing.com/larazon/2HTMHMGCVFFFDKUF2WMUPFRAW4.jpg",  folder = True ) 

    plugintools.add_item(action = "programas" , title = "[B][LOWERCASE][CAPITALIZE][COLOR white] [COLOR fuchsia]kidz [COLOR white] Baby Kidz [COLOR lime] nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",url='https://api.atresplayer.com/client/v1/row/5bc732d17ed1a82a8e1237ad?size=100&page=',page='0', thumbnail ="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2020/10/08/5AF1F499-F837-4BBA-A0B2-75BFEF221B13//720x540.jpg", fanart = "https://www.larazon.es/resizer/Obu0kOz7we-Z6QtDTC347TPFj0k=/840x0/smart/filters:format(jpg)/cloudfront-eu-central-1.images.arcpublishing.com/larazon/2HTMHMGCVFFFDKUF2WMUPFRAW4.jpg",  folder = True )  

    plugintools.add_item(action = "cine" , title = "[B][LOWERCASE][CAPITALIZE][COLOR white] [COLOR fuchsia]kidz [COLOR white] Canta con Baby Heidi [COLOR lime] nuevo[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",url='https://api.atresplayer.com/client/v1/row/5bb23a447ed1a8defc7e77e8?size=100&page=',page='0', thumbnail ="https://imagenes.atresplayer.com/atp/clipping/cmsimages01/2020/10/08/5AF1F499-F837-4BBA-A0B2-75BFEF221B13//720x540.jpg", fanart = "https://www.larazon.es/resizer/Obu0kOz7we-Z6QtDTC347TPFj0k=/840x0/smart/filters:format(jpg)/cloudfront-eu-central-1.images.arcpublishing.com/larazon/2HTMHMGCVFFFDKUF2WMUPFRAW4.jpg",  folder = True )  
    
    plugintools.add_item(action = "" , title = "[B][LOWERCASE][CAPITALIZE][COLOR yellow]-------[COLOR aqua] kidz[COLOR yellow]-------[/CAPITALIZE][/LOWERCASE][/B][/COLOR]", thumbnail =thumbnail, fanart =thumbnail,  folder = False )  

def cine(params):
    plugintools.set_view(plugintools.MOVIES,502) 
    numero = params.get("page")
    url = params.get("url")+numero
    thumbnail = params.get("thumbnail")
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body, response_headers = plugintools.read_body_and_headers(url, headers=request_headers)
    url1 = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url1,'{"title":".*?".*?pathHorizontal":".*?".*?url":".*?"')

    for generos in matches: 
        url = plugintools.find_single_match(generos,'url":".*?_(.*?)\/"')
        titulo = plugintools.find_single_match(generos,'"title":"(.*?)"')
        foto = plugintools.find_single_match(generos,'pathHorizontal":"(.*?)".*?')
        s = 'sumar'

        def dec(s):
            a = int("1")
            b = int(numero)
            suma = a+b
            return (str(suma))
        esto = dec(s) 
        plugintools.add_item(
            action="capitulo2",
            title="[B][LOWERCASE][CAPITALIZE][COLOR white]"+titulo+"[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
            thumbnail=foto,
            fanart=foto,
            url=url,
            folder=False,
            isPlayable=True
        )     
    
    if '"totalPages":1,"' in url1:
        pass   
    else:
        plugintools.add_item(
            action="programas",
            title ="[B][LOWERCASE][CAPITALIZE][COLOR lime]pagina siguiente "+esto+"[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
            thumbnail="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
            fanart="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
            url=params.get("url"),
            page=esto,
            folder=True
        ) 

def buscador(params):  
    dialog = xbmcgui.Dialog()
    d = dialog.input('[B][LOWERCASE][CAPITALIZE][COLOR orange]buscar algo: ejemplo: [COLOR white] la voz[/COLOR][/CAPITALIZE][/LOWERCASE][/B]', type=xbmcgui.INPUT_ALPHANUM).replace(" ", "+")
    d = str(d).lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    url='https://api.atresplayer.com/client/v1/row/search?entityType=ATPFormat&text='+d+'&size=100&page='
    numero = params.get("page")
    url = url+numero
    thumbnail = params.get("thumbnail")
    request_headers=[]
    request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    body,response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    url = body.strip().decode('utf-8')
    matches = plugintools.find_multiple_matches(url,'{"title":".*?".*?pathHorizontal":".*?".*?url":".*?".*?formatId":".*?"')
    
    for generos in matches: 
        formaid=plugintools.find_single_match(generos,'formatId":"(.*?)"')
        url = 'https://api.atresplayer.com/client/v1/page/format/'+formaid
        titulo = plugintools.find_single_match(generos,'"title":"(.*?)"')
        foto = plugintools.find_single_match(generos,'pathHorizontal":"(.*?)".*?')+'/1280x720.jpg'

        plugintools.add_item(
            action="temporadas",
            title ="[B][LOWERCASE][CAPITALIZE][COLOR white]"+titulo+"[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
            page=formaid,
            thumbnail=foto,
            fanart=foto,
            url=url,
            folder=True
        )     

# DONE #
def programas(params):
    plugintools.set_view(plugintools.MOVIES,502)
    thumbnail = params.get("thumbnail")
    page_number = params.get("page")
    base_url = params.get("url")

    url = f"{base_url}{page_number}"

    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0"}

    data = requests.get(url, headers=request_headers).json()
    pageInfo = data.get("pageInfo")

    for itemrow in data.get("itemRows"):
        formatid = itemrow.get("formatId")
        url = f"https://api.atresplayer.com/client/v1/page/format/{formatid}"
        title = itemrow.get("title")
        foto = itemrow.get("image").get("pathHorizontal") + "1280x720.jpg"
        plot = itemrow.get("description", "")
         
        plugintools.add_item(
            action="temporadas",
            title=f"[B][LOWERCASE][CAPITALIZE][COLOR white]{title}[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
            plot=plot,
            page=formatid,
            thumbnail=foto,
            fanart=foto,
            url=url,
            folder=True
        )

    if pageInfo.get("hasNext"):
        nextPage = str(int(page_number) + 1)
        plugintools.add_item(
            action="programas",
            title=f"[B][LOWERCASE][CAPITALIZE][COLOR lime]Next page: {nextPage}[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
            thumbnail="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
            fanart="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
            url=base_url,
            page=nextPage,
            folder=True
        )

    # request_headers=[]
    # request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])

    # body, response_headers = plugintools.read_body_and_headers( url, headers=request_headers)
    # url1 = body.strip().decode('utf-8')
    # matches = plugintools.find_multiple_matches(url1,'{"title":".*?".*?pathHorizontal":".*?".*?url":".*?".*?formatId":".*?"')

    # for generos in matches: 
    #     formaid = plugintools.find_single_match(generos,'formatId":"(.*?)"')
    #     url = 'https://api.atresplayer.com/client/v1/page/format/'+formaid
    #     titulo = plugintools.find_single_match(generos,'"title":"(.*?)"')
    #     foto = plugintools.find_single_match(generos,'pathHorizontal":"(.*?)".*?')+'/1280x720.jpg'

    #     s='sumar'
    #     def dec(s):
    #         a = int("1")
    #         b = int(numero)
    #         suma = a+b
    #         return (str(suma))

    #     esto = dec(s) 
    #     plugintools.add_item(
    #         action="temporadas",
    #         title="[B][LOWERCASE][CAPITALIZE][COLOR white]"+titulo+"[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
    #         page=formaid,
    #         thumbnail=foto,
    #         fanart=foto,
    #         url=url,
    #         folder=True
    #     )     

    # if '"totalPages":1,"' in url1: 
    #     pass  

    # else:        
    #     plugintools.add_item(
    #         action="programas",
    #         title="[B][LOWERCASE][CAPITALIZE][COLOR lime]pagina siguiente "+esto+"[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
    #         thumbnail="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
    #         fanart="https://www.periodicoelpunto.com/wp-content/uploads/2019/03/flecha-siguiente.png",
    #         url=base_url,
    #         page=esto,
    #         folder=True
    #     ) 
    
def temporadas(params):  
    plugintools.set_view(plugintools.MOVIES, 502) 
    url = params.get("url")
    formatid = params.get("page")
    thumbnail = params.get("thumbnail")

    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0"}

    seasons = requests.get(url, headers=request_headers).json().get("seasons")
    for season in seasons:
        season_url = season.get("link").get("href")
        season_data = requests.get(season_url).json()

        season_id = season_data.get("id")
        season_title = season_data.get("title")
        season_plot = season_data.get("description", "")

        plugintools.add_item(
            action="capitulos",
            plot=season_plot,
            extra="0",
            title=f"[B][LOWERCASE][CAPITALIZE][COLOR white]{season_title}[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
            page=formatid,
            thumbnail=thumbnail,
            fanart=thumbnail,
            url=season_id,
            folder=True
        )

    # request_headers = []
    # request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])

    # body,response_headers = plugintools.read_body_and_headers(url, headers=request_headers)
    # url = body.strip().decode('utf-8')

    # if '"title":"Temporada' in url:
    #     matches = plugintools.find_multiple_matches(url,'"title":"Temporada.*?".*?seasonId=.*?".*?,"pageType":"SEASON"')
    #     for generos in matches: 
    #         patron = plugintools.find_single_match(generos,'"title":"(Temporada.*?)".*?seasonId=(.*?)".*?,"pageType":"SEASON"')
    #         url = patron[1]
    #         titulo = patron[0]

    #         plugintools.add_item(
    #             action="capitulos",
    #             plot='0',
    #             title="[B][LOWERCASE][CAPITALIZE][COLOR white]"+titulo+"[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
    #             page=formaid,
    #             thumbnail=thumbnail,
    #             fanart=thumbnail,
    #             url=url,
    #             folder=True
    #         )
            
    # elif not 'season' in url:
    #     patron = plugintools.find_single_match(url,'episode":"https://api.atresplayer.com/client/v1/page/episode/(.*?)"')

    #     plugintools.add_item(
    #         action="capitulo2",
    #         title="[B][LOWERCASE][CAPITALIZE][COLOR white]reproducir[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
    #         thumbnail=thumbnail,
    #         fanart=thumbnail,
    #         url=patron,
    #         folder=False,
    #         isPlayable=True
    #     )  
    
    # else:
    #     matches = plugintools.find_multiple_matches(url,'(?i)"SEASON.*?"title":".*?".*?seasonId=.*?".*?')
    #     for generos in matches: 
    #         patron = plugintools.find_single_match(generos,'(?i)"SEASON.*?"title":"(.*?)".*?seasonId=(.*?)".*?')
    #         url = patron[1]
    #         titulo = patron[0]

    #         plugintools.add_item(
    #             action="capitulos",
    #             plot='0',
    #             title="[B][LOWERCASE][CAPITALIZE][COLOR white]"+titulo+"[/B][/COLOR][/CAPITALIZE][/LOWERCASE]",
    #             page=formaid,
    #             thumbnail=thumbnail,
    #             fanart=thumbnail,
    #             url=url,
    #             folder=True
    #         )

    #     patron = plugintools.find_single_match(url,'episode":"https://api.atresplayer.com/client/v1/page/episode/(.*?)"')
        
    #     plugintools.add_item(
    #         action="capitulo2",
    #         title ="[B][LOWERCASE][CAPITALIZE][COLOR white]reproducir[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
    #         thumbnail=thumbnail,
    #         fanart=thumbnail,
    #         url=patron,
    #         folder=False,
    #         isPlayable=True
    #     )        
    
def capitulos(params):
    plugintools.set_view(plugintools.MOVIES,502) 
    page_number = params.get("extra")        
    season_id = params.get("url")
    formatid = params.get("page")

    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0"}

    url3 = f"https://api.atresplayer.com/client/v1/row/search?entityType=ATPEpisode&formatId={formatid}&progress=true&seasonId={season_id}&size=100&page={page_number}"
    data = requests.get(url3, headers=request_headers).json()
    pageInfo = data.get("pageInfo")

    for itemrow in data.get("itemRows"):
        title = itemrow.get("title")
        plot = itemrow.get("description", "")
        foto = itemrow.get("image").get("pathHorizontal") + "1280x720.jpg"
        contentId = itemrow.get("contentId")
        
        plugintools.add_item(
            action="capitulo2",
            title=f"[B][LOWERCASE][CAPITALIZE][COLOR white]{title}[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
            plot=plot,
            thumbnail=foto,
            fanart=foto,
            url=contentId,
            folder=False,
            isPlayable=True
        )
    
    if pageInfo.get("hasNext"):
        nextPage = str(int(page_number) + 1)
        plugintools.add_item(
            action="capitulos",
            title=f"[B][LOWERCASE][CAPITALIZE][COLOR yellow]More episodes, page {nextPage}[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
            page=formatid,
            thumbnail ='',
            fanart ='',
            url=seasonId,
            extra=nextPage,
            folder=True
        )

    # mas_paginas = '&seasonId='+url9+'&size=100&page='+numero
    # url3 = 'https://api.atresplayer.com/client/v1/row/search?entityType=ATPEpisode&formatId='+formaid+'&progress=true'+mas_paginas
    # request_headers=[]
    # request_headers.append(["User-Agent","Mozilla/5.0 (Windows NT 10.0; rv:75.0) Gecko/20100101 Firefox/75.0"])
    # body, response_headers = plugintools.read_body_and_headers(url3, headers=request_headers)
    # url = body.strip().decode('utf-8')
    # siguiente = plugintools.find_single_match(url,'"hasNext":(.*?),"')
    # matches = plugintools.find_multiple_matches(url,'subTitle":".*?".*?"title":".*?".*?pathHorizontal":".*?".*?contentId":".*?".*?')
    
    # for generos in matches: 
    #     patron = plugintools.find_single_match(generos,'subTitle":".*?".*?"title":"(.*?)".*?pathHorizontal":"(.*?)".*?contentId":"(.*?)".*?')
    #     url=patron[2]
    #     titulo = patron[0]
    #     foto = patron[1]+'/1280x720.jpg'
        
    #     plugintools.add_item(
    #         action="capitulo2",
    #         title ="[B][LOWERCASE][CAPITALIZE][COLOR white]"+titulo+"[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
    #         thumbnail=foto,
    #         fanart=foto+'/1280x720.jpg',
    #         url=url,
    #         folder=False,
    #         isPlayable=True
    #     )
    
    # s='sumar'
    # def dec(s):
    #     a = int("1")
    #     b = int(numero)
    #     suma = a+b
    #     return (str(suma))

    # esto = dec(s)
    # if 'true' in siguiente:
    #     plugintools.add_item(
    #         action="capitulos",
    #         title ="[B][LOWERCASE][CAPITALIZE][COLOR yellow]mas capitulos[/CAPITALIZE][/LOWERCASE][/B][/COLOR]",
    #         page=formaid,
    #         thumbnail ='',
    #         fanart ='',
    #         url=url9,
    #         plot=esto,
    #         folder=True
    #     )


def get_subtitles(sources):
  s = [d for d in sources if "apple.mpegurl" in d.get("type")]
  if s:
    link = s[0].get("src")
    r = requests.get(link)
    if r.status_code == 200:
      lines = r.text.split("\n")
      for l in lines:
        if "type=subtitles" in l.lower():
          sublink = dict([tuple(v.split("=")) for v in l.split(",")]).get("URI")
          if sublink:
            sublink = "/".join(link.split("/")[:-1]) + "/" + sublink.replace('"', "")
            r2 = requests.get(sublink)
            if r2.status_code == 200:
              return ["/".join(sublink.split("/")[:-1]) + "/" + [l for l in r2.text.split("\n") if not l.startswith("#EXT")][0]]


  return []

def capitulo2(params):
    contentId = params.get("url")
    ep_url = f"https://api.atresplayer.com/player/v1/episode/{contentId}"

    cookies1 = "A3PSID=Stymkcj3c3SliN80TgRiUC-DujNKlYqu94_ChJhi0yavvUBH8L3KTb7TrYPku-ymLmkFDgP7n1GCw4cmAbeVrg"
    cookies2 = "A3PSID=e-K43h4C-mHt2iEuwLAjVBQZRI9fbQ8wwZqywYUw10cw_Q5zUt3qTe-eeC95gIqOtn4lQECSD94C3bjk1r2AVA"
    cookies3 = "A3PSID=odLLXJN_8n5HO8W9Mc-uWExfUJwg_7hPFgPDKtKWhVjKjAzSfciw2GJehl8SPV-kEbsYw5YfcaGRgaiFKSOnNg"

    headers1 = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
            "Accept": "*/*",
            "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3","referer":"https://www.atresplayer.com/documentales/pongamos-que-hablo-de-sabina/temporada-1/capitulo-1-los-pecados_5ebbdbbd7ed1a8354e4201d3/",
            "cookie": cookies1
    }

    headers2 = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
        "Accept": "*/*",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3","referer":"https://www.atresplayer.com/documentales/pongamos-que-hablo-de-sabina/temporada-1/capitulo-1-los-pecados_5ebbdbbd7ed1a8354e4201d3/",
        "cookie": cookies2
    }
        
    headers3 = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
        "Accept": "*/*",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3","referer":"https://www.atresplayer.com/documentales/pongamos-que-hablo-de-sabina/temporada-1/capitulo-1-los-pecados_5ebbdbbd7ed1a8354e4201d3/",
        "cookie": cookies3
    }

    viva = {"http": "http://14.139.189.213:3128"}

    for h in [headers3, headers1, headers2]:
        resp = requests.get(ep_url, proxies=viva, headers=h)
        status_code = resp.status_code
        print(status_code)
        if status_code == 200:
            data = resp.json()
            break

    sources = data.get("sources")

    # url = [d for d in sources if "smooth.smil" in d.get("src")][0].get("src")
    url = [d for d in sources if "hls+legacy" in d.get("type")][0].get("src")
    subs = get_subtitles(sources)
    
    play_headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
        }

    plugintools.play_resolved_url(
            url=url,
            subtitles=subs,
            headers=play_headers,
            subtitle_offset=-1,
    )


    # plugintools.log("atresplayer.capitulo2 "+repr(params))      
    # url = 'https://pastebin.com/raw/Th0mgdXX'
    # headers= {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0"}
    # url = requests.get(url,headers=headers,verify=False,timeout=5).text
    # cookies1 = plugintools.find_single_match(url,'"(.*?)"')

    # url = 'https://pastebin.com/raw/kCKm22hH'
    # headers= {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0"}
    # url = requests.get(url,headers=headers,verify=False,timeout=5).text
    # cookies2 = plugintools.find_single_match(url,'"(.*?)"')

    # url = 'https://pastebin.com/raw/cZRp0kgP'
    # headers= {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0"}
    # url = requests.get(url,headers=headers,verify=False,timeout=5).text
    # cookies3 = plugintools.find_single_match(url,'"(.*?)"')

    # headers1 = {
    #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
    #     "Accept": "*/*",
    #     "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3","referer":"https://www.atresplayer.com/documentales/pongamos-que-hablo-de-sabina/temporada-1/capitulo-1-los-pecados_5ebbdbbd7ed1a8354e4201d3/",
    #     "cookie": cookies1
    # }
    
    # headers2 = {
    #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
    #     "Accept": "*/*",
    #     "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3","referer":"https://www.atresplayer.com/documentales/pongamos-que-hablo-de-sabina/temporada-1/capitulo-1-los-pecados_5ebbdbbd7ed1a8354e4201d3/",
    #     "cookie": cookies2
    # }
        
    # headers3 = {
    #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
    #     "Accept": "*/*",
    #     "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3","referer":"https://www.atresplayer.com/documentales/pongamos-que-hablo-de-sabina/temporada-1/capitulo-1-los-pecados_5ebbdbbd7ed1a8354e4201d3/",
    #     "cookie": cookies3
    # }
    
    # viva = {"http": "http://14.139.189.213:3128"}
    # esto = requests.get("https://api.atresplayer.com/player/v1/episode/"+params.get("url"), proxies=viva, headers=headers1).text 
   
    # if "m3u8" in str(esto):
    #     esto = esto
                   
    # else:
    #     esto = requests.get("https://api.atresplayer.com/player/v1/episode/"+params.get("url"), proxies=viva, headers=headers2).text  
        
    #     if "m3u8" in str(esto):
    #         esto = esto
        
    #     else:
    #         esto = requests.get("https://api.atresplayer.com/player/v1/episode/"+params.get("url"),proxies=viva, headers=headers3).text  
    
    # url = plugintools.find_single_match(esto,'src":"(.*?m3u8.*?)".*?').replace('drm','')+'|user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36'
    # plugintools.play_resolved_url(url)

# def play_movie_with_mpd(mpd_url):

#     """Reproduce la película usando el protocolo mpd."""
#     play_item = xbmcgui.ListItem(path=url)
    
#     # Configurar el inputstream para mpd
#     PROTOCOL = 'mpd'
#     is_helper = inputstreamhelper.Helper(PROTOCOL)

#     if not is_helper.check_inputstream():
#         xbmcgui.Dialog().notification("Error", "No se encontró un complemento compatible para MPD.", xbmcgui.NOTIFICATION_ERROR)
#         return

#     # Establecer las propiedades necesarias para el streaming
#     play_item.setMimeType('application/x-mpegurl')
#     play_item.setContentLookup(False)
#     play_item.setProperty("inputstream", is_helper.inputstream_addon)
#     play_item.setProperty("IsPlayable", "true")
#     play_item.setProperty('inputstream.adaptive.manifest_type', PROTOCOL)

#     # Configurar subtítulos (si es necesario)
#     play_item.setSubtitles(['special://home/subtitulos.srt'])

#     # Reproducir el video
#     xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem=play_item)

def play(params):            
    url = params.get("url") + '|user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36'
    plugintools.play_resolved_url(url)    
    
run()