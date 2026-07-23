"""
TorBox WebDAV Kodi Plugin
Refactored entrypoint that focuses on UI listing and routing.
"""

import os
from urllib.parse import unquote

import xbmc
import xbmcgui
import xbmcplugin

from torbox_common import (
    ADDON,
    APP_NAME,
    HANDLE,
    MAX_ACCOUNTS,
    SKIP_EXTS,
    VIDEO_EXTS,
    VIDEO_MIMETYPES,
    build_url,
    clean_show_name,
    extract_episode_info,
    get_account,
    get_accounts,
    get_params,
    import_overrides,
    load_overrides,
    log,
    save_overrides,
    export_overrides,
    search_catalog,
    search_streams,
)
from torbox_library import export_library, export_library_item
from torbox_setup import add_account
from torbox_subtitles import add_subtitles, find_local_subtitles, search_subs_imdb_id
from torbox_tmdb import get_tvdb_id_from_tmdb, search_tmdb_movies, search_tmdb_tvshows
from torbox_text import (
    CONTEXT_ADD_SUBTITLES,
    CONTEXT_EXPORT_SINGLE_ITEM,
    CONTEXT_REFRESH_LIBRARY,
    CONTEXT_SET_OVERRIDE,
    DIALOG_MANUAL_TMDB,
    DIALOG_OVERRIDES_DELETE_BODY,
    DIALOG_OVERRIDES_DELETE_TITLE,
    DIALOG_OVERRIDES_EMPTY,
    DIALOG_OVERRIDES_SELECT_DELETE,
    DIALOG_OVERRIDES_TITLE,
    DIALOG_PICK_TMDB,
    DIALOG_SET_CONTENT_TYPE,
    DIALOG_SET_TITLE,
    DIALOG_SET_TMDB,
    DIALOG_SET_TVDB,
    DIALOG_SET_YEAR,
    LABEL_GRAY_ITEM,
    LABEL_MEDIA_FOLDER,
    LABEL_MEDIA_UNKNOWN,
    MENU_ACCOUNT_BROWSE,
    MENU_ACCOUNT_EXPORT,
    MENU_ADD_ACCOUNT,
    MENU_IMPORT_OVERRIDES,
    MENU_MANAGE_OVERRIDES,
    MENU_EXPORT_OVERRIDES,
    MENU_SEARCH,
    MENU_SETTINGS,
    NOTIFY_ACCOUNT_NOT_FOUND,
    NOTIFY_OVERRIDE_REMOVED,
    NOTIFY_OVERRIDE_SAVED,
    NOTIFY_SEARCHING_TMDB,
)
from torbox_webdav import build_authed_url, parse_propfind, propfind


def list_accounts():
    accounts = get_accounts()
    next_acc = 1

    for acc in accounts:
        li = xbmcgui.ListItem(label=MENU_ACCOUNT_BROWSE.format(acc['name']))
        li.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
        li.setInfo('video', {'title': acc['name'], 'plot': 'Browse files directly'})
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({'action': 'browse', 'account': acc['index'], 'path': '/'}),
            li,
            isFolder=True,
        )

        li = xbmcgui.ListItem(label=MENU_ACCOUNT_EXPORT.format(acc['name']))
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({'action': 'export_library', 'account': acc['index']}),
            li,
            isFolder=False,
        )

        next_acc = int(acc['index']) + 1

    if next_acc <= MAX_ACCOUNTS:
        li = xbmcgui.ListItem(label=MENU_ADD_ACCOUNT.format(next_acc))
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({'action': 'add_account', 'account': next_acc}),
            li,
            isFolder=False,
        )

    li = xbmcgui.ListItem(label=MENU_SEARCH)
    xbmcplugin.addDirectoryItem(HANDLE, build_url({'action': 'search_menu'}), li, isFolder=True)

    li = xbmcgui.ListItem(label=MENU_MANAGE_OVERRIDES)
    xbmcplugin.addDirectoryItem(HANDLE, build_url({'action': 'view_overrides'}), li, isFolder=False)

    li = xbmcgui.ListItem(label=MENU_EXPORT_OVERRIDES)
    xbmcplugin.addDirectoryItem(HANDLE, build_url({'action': 'export_overrides'}), li, isFolder=False)

    li = xbmcgui.ListItem(label=MENU_IMPORT_OVERRIDES)
    xbmcplugin.addDirectoryItem(HANDLE, build_url({'action': 'import_overrides'}), li, isFolder=False)

    li = xbmcgui.ListItem(label=MENU_SETTINGS)
    xbmcplugin.addDirectoryItem(HANDLE, build_url({'action': 'settings'}), li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


def list_directory(account_index, remote_path, is_library_root=False):
    account = get_account(account_index)
    if not account:
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_ACCOUNT_NOT_FOUND, xbmcgui.NOTIFICATION_ERROR)
        return

    xml_root = propfind(account['url'] + remote_path, account['username'], account['password'], depth=1)
    if xml_root is None:
        return

    items = parse_propfind(xml_root, account['url'], remote_path)
    overrides = load_overrides()
    show_hidden = ADDON.getSettingBool('show_hidden')

    if is_library_root:
        xbmcplugin.setContent(HANDLE, 'tvshows')
    else:
        has_collections = any(item['is_collection'] for item in items)
        has_video = any(os.path.splitext(item['name'])[1].lower() in VIDEO_EXTS for item in items if not item['is_collection'])
        if has_collections:
            xbmcplugin.setContent(HANDLE, 'tvshows')
        elif has_video:
            xbmcplugin.setContent(HANDLE, 'episodes')
        else:
            xbmcplugin.setContent(HANDLE, 'files')

    for item in sorted(items, key=lambda x: (not x['is_collection'], x['name'].lower())):
        name = item['name']

        if not show_hidden and name.startswith('.'):
            continue

        ext = os.path.splitext(name)[1].lower()

        if item['is_collection']:
            child_path = unquote(item['path'])
            if not child_path.endswith('/'):
                child_path += '/'

            override = overrides.get(name, {})
            thumb_url = ''
            plot = ''
            if override:
                clean_title = override.get('title', name)
                year = override.get('year')
                tvdb_id = override.get('tvdb_id', '')
                tmdb_id = override.get('tmdb_id', '')
                thumb_url = override.get('thumb', '')
                plot = override.get('plot', '')
                media_type = override.get('type', 'tvshow')
                display_label = LABEL_MEDIA_FOLDER.format(media_type, clean_title)
            else:
                clean_title, year = clean_show_name(name)
                tvdb_id = ''
                tmdb_id = ''
                media_type = 'tvshow'
                display_label = LABEL_MEDIA_UNKNOWN.format("unknown", clean_title)

            if year:
                display_label = '{} ({})'.format(display_label, year)
            if tmdb_id:
                display_label = '{} [{}]'.format(display_label, tmdb_id)
            if tvdb_id:
                display_label = display_label + " {" + tvdb_id + "}"

            li = xbmcgui.ListItem(label=display_label)
            info = {
                'title': display_label,
                'tvshowtitle': clean_title,
                'originaltitle': clean_title,
                'sorttitle': clean_title,
                'mediatype': media_type,
                'plot': plot or clean_title,
            }
            if year:
                info['year'] = year

            try:
                li.setUniqueIDs({'tvdb': tvdb_id, 'tmdb': tmdb_id}, defaultUniqueID='tvdb' if tvdb_id else 'tmdb')
            except Exception:
                pass

            li.addContextMenuItems(
                [
                    (
                        CONTEXT_SET_OVERRIDE,
                        'RunPlugin({})'.format(
                            build_url({'action': 'set_override', 'folder_name': name, 'account': account_index})
                        ),
                    ),
                    (
                        CONTEXT_ADD_SUBTITLES,
                        'RunPlugin({})'.format(
                            build_url({'action': 'add_subtitles', 'folder_name': name, 'account': account_index})
                        ),
                    ),
                    (
                        CONTEXT_EXPORT_SINGLE_ITEM,
                        'RunPlugin({})'.format(
                            build_url(
                                {
                                    'action': 'export_item',
                                    'folder_name': name,
                                    'path': child_path,
                                    'account': account_index,
                                }
                            )
                        ),
                    ),
                    (
                        CONTEXT_REFRESH_LIBRARY,
                        'RunPlugin({})'.format(build_url({'action': 'refresh', 'folder_name': name})),
                    ),
                ]
            )

            art = {'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'}
            if thumb_url:
                art.update({'thumb': thumb_url, 'icon': thumb_url, 'poster': thumb_url})
            li.setArt(art)
            li.setInfo('video', info)
            xbmcplugin.addDirectoryItem(
                HANDLE,
                build_url(
                    {
                        'action': 'browse',
                        'account': account_index,
                        'path': child_path,
                        'library': '1' if is_library_root else '0',
                    }
                ),
                li,
                isFolder=True,
            )
            continue

        if ext in VIDEO_EXTS:
            season, episode = extract_episode_info(name)
            li = xbmcgui.ListItem(label=name)

            info = {'title': name, 'mediatype': 'episode'}
            if season is not None:
                info['season'] = season
                info['episode'] = episode

            li.setInfo('video', info)
            li.setArt({'icon': 'DefaultVideo.png', 'thumb': 'DefaultVideo.png'})
            li.setProperty('IsPlayable', 'true')

            mime = VIDEO_MIMETYPES.get(ext)
            if mime:
                li.setMimeType(mime)
                li.setContentLookup(False)

            xbmcplugin.addDirectoryItem(
                HANDLE,
                build_url({'action': 'play', 'account': account_index, 'url': item['full_url']}),
                li,
                isFolder=False,
            )
            continue

        if ext in SKIP_EXTS:
            continue

        li = xbmcgui.ListItem(label=LABEL_GRAY_ITEM.format(name))
        li.setInfo('video', {'title': name})
        xbmcplugin.addDirectoryItem(HANDLE, item['full_url'], li, isFolder=False)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def play_item(account_index, stream_url, strm_path=None):
    account = get_account(account_index)
    if not account:
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_ACCOUNT_NOT_FOUND, xbmcgui.NOTIFICATION_ERROR)
        return

    authed_url = build_authed_url(stream_url, account['username'], account['password'])
    li = xbmcgui.ListItem(path=authed_url)

    ext = os.path.splitext(stream_url)[1].lower()
    mime = VIDEO_MIMETYPES.get(ext)
    if mime:
        li.setMimeType(mime)
        li.setContentLookup(False)

    local_subs = find_local_subtitles(strm_path) if strm_path else []
    li.setSubtitles(local_subs)
    log('Local subtitles: {}'.format(local_subs))

    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def play_search(stream_url, imdb_id=None):

    subtitle_lang_options = ["eng", "spa"]
    subs = []
    if imdb_id:
        lang_idx = xbmcgui.Dialog().select("Select subtitle language", subtitle_lang_options)
        if lang_idx >= 0:
            subtitle_lang = subtitle_lang_options[lang_idx]
            subs = search_subs_imdb_id(imdb_id, subtitle_lang)

    li = xbmcgui.ListItem(path=stream_url)
    li.setSubtitles(subs)
    log('Found subtitles: {}'.format(subs))
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def _show_search_error(context, exc):
    message = '{}: {}'.format(type(exc).__name__, exc)
    log('Search error in {}: {}'.format(context, message), xbmc.LOGERROR)
    xbmcgui.Dialog().notification(
        APP_NAME,
        'Search error in {}. Check Kodi log.'.format(context),
        xbmcgui.NOTIFICATION_ERROR,
    )


def search_results(search_query):
    log('Search results query="{}"'.format(search_query))
    xbmcplugin.setContent(HANDLE, 'movies')

    new_search_item = xbmcgui.ListItem(label=f'Search again. Your search: "{search_query}"')
    xbmcplugin.addDirectoryItem(
                HANDLE,
                build_url({'action': 'search'}),
                new_search_item,
                isFolder=True,
            )
    
    try:
        results = search_catalog(search_query)

        if not results:
            xbmcgui.Dialog().notification(
                APP_NAME,
                'No results found for "{}"'.format(search_query),
                xbmcgui.NOTIFICATION_INFO,
            )
            xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
            return

        for result in results:
            title = result.get('name', 'Unknown Title')
            release_info = result.get('releaseInfo')
            year_text = ' ({})'.format(release_info) if release_info else ''
            imdb_id = result.get('imdb_id', '')

            li = xbmcgui.ListItem(
                label='{}{}'.format(title, year_text),
                label2='IMDB {}'.format(imdb_id) if imdb_id else '',
            )
            poster_url = result.get('poster')
            if poster_url:
                li.setArt({'icon': poster_url, 'thumb': poster_url, 'poster': poster_url})
            li.setInfo(
                'video',
                {
                    'title': title,
                    'plot': result.get('plot', title),
                    'mediatype': 'movie',
                },
            )

            xbmcplugin.addDirectoryItem(
                HANDLE,
                build_url(
                    {
                        'action': 'search_streams',
                        'imdb_id': imdb_id,
                        'title': title,
                        'query': search_query,
                    }
                ),
                li,
                isFolder=True,
            )

        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
    except Exception as exc:
        _show_search_error('search_results', exc)
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def list_search_streams(imdb_id, title='', search_query=''):
    try:
        streams = search_streams(imdb_id)

        if not streams:
            xbmcgui.Dialog().notification(
                APP_NAME,
                'No streams found for "{}"'.format(title or search_query or imdb_id),
                xbmcgui.NOTIFICATION_INFO,
            )
            xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
            return

        xbmcplugin.setContent(HANDLE, 'videos')

        for result in streams:
            stream_url = result.get('url', '')
            if not stream_url:
                continue

            raw_name = result.get('name')
            name = raw_name.strip() if isinstance(raw_name, str) else ''
            raw_description = result.get('description')
            description = raw_description.strip() if isinstance(raw_description, str) else ''

            label2 = description
            file_name = ''
            if 'FILENAME=' in description:
                label2, file_name = description.split('FILENAME=', 1)
                label2 = label2.strip()
                file_name = file_name.strip()

            label = name or 'Unknown Stream'
            if file_name:
                label = '{} {}'.format(label, file_name)

            li = xbmcgui.ListItem(label=label, label2=label2)
            li.setProperty('IsPlayable', 'true')

            ext = os.path.splitext(stream_url)[1].lower()
            mime = VIDEO_MIMETYPES.get(ext)
            if mime:
                li.setMimeType(mime)
                li.setContentLookup(False)

            li.setInfo(
                'video',
                {
                    'title': label,
                    'plot': label2 or label,
                    'mediatype': 'video',
                },
            )

            xbmcplugin.addDirectoryItem(
                HANDLE,
                build_url({'action': 'play_search', 'url': stream_url, 'imdb_id': imdb_id}),
                li,
                isFolder=False,
            )

        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
    except Exception as exc:
        _show_search_error('search_streams', exc)
        try:
            xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        except Exception:
            pass

def search_menu():
    xbmcplugin.setContent(HANDLE, 'movies')

    li = xbmcgui.ListItem(label='New Search')
    li.setArt({'icon': 'DefaultAddonsSearch.png'})
    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url({'action': 'search'}),
        li,
        isFolder=True,
    )

    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)

def search():
    keyboard = xbmc.Keyboard('', APP_NAME)
    keyboard.doModal()

    if not keyboard.isConfirmed():
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True, cacheToDisc=False)
        return

    query = keyboard.getText().strip()
    if not query:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True, cacheToDisc=False)
        return

    url = build_url({'action': 'search_results', 'query': query})
    log('Search redirect query="{}" url={}'.format(query, url))

    xbmcplugin.endOfDirectory(HANDLE, succeeded=True, cacheToDisc=False)

    xbmc.sleep(500)  # let the GUI finish deiniting the current window before redirecting
    xbmc.executebuiltin('Container.Update({},replace)'.format(url))


def choose_tmdb_movie(title, year=None, existing_tmdb_id=''):
    dialog = xbmcgui.Dialog()
    manual_default = existing_tmdb_id or ''

    dialog.notification(APP_NAME, NOTIFY_SEARCHING_TMDB, xbmcgui.NOTIFICATION_INFO, 2000)
    results = search_tmdb_movies(title, year)

    if not results:
        manual_tmdb_id = dialog.input(DIALOG_SET_TMDB, defaultt=manual_default)
        if manual_tmdb_id is None:
            return None
        return {'id': manual_tmdb_id, 'year': None, 'poster_url': ''}

    options = []
    for result in results:
        year_text = ' ({})'.format(result['year']) if result.get('year') else ''
        item = xbmcgui.ListItem(
            label='{}{}'.format(result['title'], year_text),
            label2='TMDB {}'.format(result['id']),
        )
        poster_url = result.get('poster_url')
        if poster_url:
            item.setArt({'icon': poster_url, 'thumb': poster_url})
        options.append(item)

    options.append(
        xbmcgui.ListItem(
            label=DIALOG_MANUAL_TMDB,
            label2='TMDB {}'.format(manual_default) if manual_default else '',
        )
    )

    choice = dialog.select(DIALOG_PICK_TMDB.format(title[:40]), options, useDetails=True)
    if choice < 0:
        return None

    if choice == len(results):
        manual_tmdb_id = dialog.input(DIALOG_SET_TMDB, defaultt=manual_default)
        if manual_tmdb_id is None:
            return None
        return {'id': manual_tmdb_id, 'year': None, 'poster_url': ''}

    selected = results[choice]
    return {
        'id': selected['id'],
        'year': selected.get('year'),
        'poster_url': selected.get('poster_url', ''),
        'plot': selected.get('plot', ''),
    }


def choose_tmdb_tvshow(title, year=None, existing_tmdb_id=''):
    dialog = xbmcgui.Dialog()
    manual_default = existing_tmdb_id or ''

    dialog.notification(APP_NAME, NOTIFY_SEARCHING_TMDB, xbmcgui.NOTIFICATION_INFO, 2000)
    results = search_tmdb_tvshows(title, year)

    if not results:
        manual_tmdb_id = dialog.input(DIALOG_SET_TMDB, defaultt=manual_default)
        if manual_tmdb_id is None:
            return None
        return {'id': manual_tmdb_id, 'year': None, 'poster_url': ''}

    options = []
    for result in results:
        year_text = ' ({})'.format(result['year']) if result.get('year') else ''
        item = xbmcgui.ListItem(
            label='{}{}'.format(result['title'], year_text),
            label2='TMDB {}'.format(result['id']),
        )
        poster_url = result.get('poster_url')
        if poster_url:
            item.setArt({'icon': poster_url, 'thumb': poster_url})
        options.append(item)

    options.append(
        xbmcgui.ListItem(
            label=DIALOG_MANUAL_TMDB,
            label2='TMDB {}'.format(manual_default) if manual_default else '',
        )
    )

    choice = dialog.select(DIALOG_PICK_TMDB.format(title[:40]), options, useDetails=True)
    if choice < 0:
        return None

    if choice == len(results):
        manual_tmdb_id = dialog.input(DIALOG_SET_TMDB, defaultt=manual_default)
        if manual_tmdb_id is None:
            return None
        return {'id': manual_tmdb_id, 'year': None, 'poster_url': ''}

    selected = results[choice]
    return {
        'id': selected['id'],
        'year': selected.get('year'),
        'poster_url': selected.get('poster_url', ''),
        'plot': selected.get('plot', ''),
    }


def set_override(folder_name, account_index):
    del account_index

    overrides = load_overrides()
    existing = overrides.get(folder_name, {})
    clean_guess, year_guess = clean_show_name(folder_name)

    dialog = xbmcgui.Dialog()

    title = dialog.input(
        DIALOG_SET_TITLE.format(folder_name[:60]),
        defaultt=existing.get('title', clean_guess),
    )
    if title is None:
        return

    title = title.strip()

    year_str = dialog.input(
        DIALOG_SET_YEAR,
        defaultt=str(existing.get('year', year_guess or '')),
        type=xbmcgui.INPUT_NUMERIC,
    )

    current_type = existing.get('type', 'tvshow')
    type_choices = ['TV Show', 'Movie']
    type_default = 1 if current_type == 'movie' else 0
    type_choice = dialog.select(DIALOG_SET_CONTENT_TYPE.format(title[:40]), type_choices, preselect=type_default)
    if type_choice < 0:
        return

    media_type = 'movie' if type_choice == 1 else 'tvshow'

    tvdb_id = ''
    tmdb_id = ''
    tmdb_thumb = ''
    year_value = None
    if year_str:
        try:
            year_value = int(year_str)
        except ValueError:
            year_value = None

    if media_type == 'tvshow':
        tmdb_choice = choose_tmdb_tvshow(
            title,
            year=year_value,
            existing_tmdb_id=existing.get('tmdb_id', ''),
        )
        if tmdb_choice is None:
            # User cancelled TMDB selection, show TVDB dialog as fallback
            tvdb_id = dialog.input(
                DIALOG_SET_TVDB,
                defaultt=existing.get('tvdb_id', ''),
            )
            if tvdb_id is None:
                return
        else:
            tmdb_id = tmdb_choice.get('id', '')
            tmdb_year = tmdb_choice.get('year')
            tmdb_thumb = tmdb_choice.get('poster_url', '')
            tmdb_plot = tmdb_choice.get('plot', '')
            if tmdb_year is not None and tmdb_year != year_value:
                year_value = tmdb_year

            # Try to fetch TVDB ID from TMDB
            tvdb_id = get_tvdb_id_from_tmdb(tmdb_id) or ''

            # If TVDB ID not found, show TVDB dialog as fallback
            if not tvdb_id:
                tvdb_id = dialog.input(
                    DIALOG_SET_TVDB,
                    defaultt=existing.get('tvdb_id', ''),
                )
                if tvdb_id is None:
                    return
    else:
        tmdb_choice = choose_tmdb_movie(
            title,
            year=year_value,
            existing_tmdb_id=existing.get('tmdb_id', ''),
        )
        if tmdb_choice is None:
            return
        tmdb_id = tmdb_choice.get('id', '')
        tmdb_year = tmdb_choice.get('year')
        tmdb_thumb = tmdb_choice.get('poster_url', '')
        tmdb_plot = tmdb_choice.get('plot', '')
        if tmdb_year is not None and tmdb_year != year_value:
            year_value = tmdb_year

    entry = {'title': title, 'type': media_type}
    if year_value is not None:
        entry['year'] = year_value

    if tvdb_id and tvdb_id.strip():
        entry['tvdb_id'] = tvdb_id.strip()
    if tmdb_id and tmdb_id.strip():
        entry['tmdb_id'] = tmdb_id.strip()
    if media_type in ('movie', 'tvshow'):
        if tmdb_thumb:
            entry['thumb'] = tmdb_thumb
        elif existing.get('thumb'):
            entry['thumb'] = existing['thumb']
        if tmdb_plot:
            entry['plot'] = tmdb_plot
        elif existing.get('plot'):
            entry['plot'] = existing['plot']
    if existing.get('subs'):
        entry['subs'] = existing['subs']

    overrides[folder_name] = entry
    save_overrides(overrides)

    xbmcgui.Dialog().notification(
        APP_NAME,
        NOTIFY_OVERRIDE_SAVED.format(title, media_type),
        xbmcgui.NOTIFICATION_INFO,
        3000,
    )


def view_overrides():
    overrides = load_overrides()
    if not overrides:
        xbmcgui.Dialog().ok(
            DIALOG_OVERRIDES_TITLE.format(APP_NAME),
            DIALOG_OVERRIDES_EMPTY,
        )
        return

    items = list(overrides.items())
    labels = [
        '{} -> {} ({}) [{}]'.format(
            folder_name[:40],
            entry.get('title', '?'),
            entry.get('year', '?'),
            entry.get('type', 'tvshow'),
        )
        for folder_name, entry in items
    ]

    idx = xbmcgui.Dialog().select(DIALOG_OVERRIDES_SELECT_DELETE.format(APP_NAME), labels)
    if idx < 0:
        return

    folder_name, entry = items[idx]
    if xbmcgui.Dialog().yesno(DIALOG_OVERRIDES_DELETE_TITLE, DIALOG_OVERRIDES_DELETE_BODY.format(entry.get('title', folder_name))):
        del overrides[folder_name]
        save_overrides(overrides)
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_OVERRIDE_REMOVED, xbmcgui.NOTIFICATION_INFO, 2000)


def _get_account_param(params):
    try:
        return max(1, int(params.get('account', 1)))
    except (TypeError, ValueError):
        return 1


def router():
    params = get_params()
    action = params.get('action', 'root')
    log('Action={} Params={}'.format(action, params))

    if action == 'root':
        list_accounts()
    elif action == 'browse':
        list_directory(_get_account_param(params), params.get('path', '/'), params.get('library', '0') == '1')
    elif action == 'library_browse':
        account_index = _get_account_param(params)
        path = params.get('path', '/')
        list_directory(account_index, path, is_library_root=(path == '/'))
    elif action == 'play':
        play_item(_get_account_param(params), params.get('url', ''), params.get('strm'))
    elif action == 'play_search':
        play_search(params.get('url', ''), params.get('imdb_id'))
    elif action == 'set_override':
        set_override(params.get('folder_name', ''), _get_account_param(params))
    elif action == 'add_subtitles':
        add_subtitles(params.get('folder_name', ''), _get_account_param(params))
    elif action == 'view_overrides':
        view_overrides()
    elif action == 'export_overrides':
        export_overrides()
    elif action == 'import_overrides':
        import_overrides()
    elif action == 'search_menu':
        search_menu()
    elif action == 'search':
        search()
    elif action == 'search_results':
        search_results(params.get('query', ''))
    elif action == 'search_streams':
        list_search_streams(
            params.get('imdb_id', ''),
            params.get('title', ''),
            params.get('query', ''),
        )
    elif action == 'add_account':
        add_account(_get_account_param(params))
    elif action == 'settings':
        ADDON.openSettings()
    elif action == 'refresh':
        xbmc.executebuiltin('UpdateLibrary(video)')
    elif action == 'export_library':
        export_library(_get_account_param(params))
    elif action == 'export_item':
        export_library_item(
            _get_account_param(params),
            params.get('folder_name', ''),
            params.get('path', ''),
        )
    else:
        log('Unknown action: {}'.format(action), xbmc.LOGWARNING)
        list_accounts()


if __name__ == '__main__':
    router()
