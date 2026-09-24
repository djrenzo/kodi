import os
from urllib.request import Request, urlopen

import xbmc
import xbmcgui
import xbmcvfs

from torbox_common import ADDON, APP_NAME, extract_episode_info, get_account, load_overrides, log, make_auth_header
from torbox_http import download as download_text
from torbox_library import (
    episode_basename,
    find_main_video,
    get_media_library_root,
    join_path,
    movie_folder_name,
    normalize_collection_path,
    resolve_media_info,
    walk_webdav,
    write_movie_nfo,
    write_tvshow_nfo,
)
from torbox_text import (
    DIALOG_DOWNLOAD_CONFIRM,
    DIALOG_DOWNLOAD_DONE,
    DIALOG_DOWNLOAD_NO_VIDEOS,
    DIALOG_DOWNLOAD_PATH_NOT_CONFIGURED,
    NOTIFY_ACCOUNT_NOT_FOUND,
    NOTIFY_DOWNLOAD_CANCELLED,
    PROGRESS_DOWNLOAD_FILE,
    PROGRESS_DOWNLOAD_TITLE,
)
from torbox_webdav import encode_webdav_url

CHUNK_SIZE = 1024 * 1024
DOWNLOAD_TIMEOUT = 60
PARTIAL_SUFFIX = '.part'


class DownloadCancelled(Exception):
    pass


def get_download_path():
    path = ADDON.getSettingString('download_path')
    if not path:
        xbmcgui.Dialog().ok(APP_NAME, DIALOG_DOWNLOAD_PATH_NOT_CONFIGURED)
        return None
    # translatePath resolves special:// and leaves smb:// (and other VFS URLs) untouched.
    return xbmcvfs.translatePath(path)


def _format_size(size):
    size = float(size or 0)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024:
            return '{:.1f} {}'.format(size, unit)
        size /= 1024
    return '{:.1f} TB'.format(size)


def _ensure_folder(folder):
    if not xbmcvfs.exists(folder + '/'):
        xbmcvfs.mkdirs(folder)


def _existing_size(path):
    if not xbmcvfs.exists(path):
        return -1
    try:
        return xbmcvfs.Stat(path).st_size()
    except Exception:
        return -1


def _plan_downloads(account, info, remote_path, download_root):
    """Mirror the STRM export layout: returns (folder, [(webdav item, dest path)])."""
    ext_of = lambda item: os.path.splitext(item['name'])[1].lower()

    if info['media_type'] == 'movie':
        folder_name = movie_folder_name(info['title'], info['year'])
        folder = join_path(get_media_library_root(download_root, 'movie'), folder_name)
        video_item = find_main_video(account, remote_path)
        if video_item is None or ext_of(video_item) == '.strm':
            return folder, []
        return folder, [(video_item, join_path(folder, folder_name + ext_of(video_item)))]

    folder = join_path(get_media_library_root(download_root, 'tvshow'), info['title'])
    jobs = []
    for episode in walk_webdav(account, remote_path):
        if ext_of(episode) == '.strm':
            continue
        season, episode_no = extract_episode_info(episode['name'])
        if season is None:
            continue
        basename = episode_basename(info['title'], season, episode_no)
        jobs.append((episode, join_path(folder, basename + ext_of(episode))))
    return folder, jobs


def _download_file(account, item, dest_path, on_progress):
    """Stream a WebDAV file to dest_path via xbmcvfs (works for local and smb:// targets)."""
    temp_path = dest_path + PARTIAL_SUFFIX
    request = Request(
        encode_webdav_url(item['full_url']),
        headers={
            'Authorization': make_auth_header(account['username'], account['password']),
            'User-Agent': 'Kodi/TorBox-Plugin',
        },
    )
    monitor = xbmc.Monitor()

    try:
        response = urlopen(request, timeout=DOWNLOAD_TIMEOUT)
        total = int(response.headers.get('Content-Length') or item.get('size') or 0)
        written = 0

        out_file = xbmcvfs.File(temp_path, 'w')
        try:
            while True:
                if monitor.abortRequested():
                    raise DownloadCancelled()
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                if not out_file.write(bytearray(chunk)):
                    raise IOError('write failed for {}'.format(temp_path))
                written += len(chunk)
                on_progress(written, total)
        finally:
            out_file.close()
            response.close()

        if total and written != total:
            raise IOError('incomplete download: {} of {} bytes'.format(written, total))

        if xbmcvfs.exists(dest_path):
            xbmcvfs.delete(dest_path)
        if not xbmcvfs.rename(temp_path, dest_path):
            raise IOError('could not rename {} to {}'.format(temp_path, dest_path))
        return True
    except DownloadCancelled:
        xbmcvfs.delete(temp_path)
        raise
    except Exception as exc:
        log('Download failed for {}: {}'.format(item['full_url'], exc), xbmc.LOGERROR)
        xbmcvfs.delete(temp_path)
        return False


def _download_subtitles(folder, subs):
    saved = 0
    for sub in subs:
        url = sub.get('url')
        file_name = sub.get('fileName')
        if not url or not file_name:
            continue
        if download_text(url, join_path(folder, file_name)):
            saved += 1
        else:
            log('Subtitle download failed: {}'.format(url), xbmc.LOGWARNING)
    return saved


def download_library_item(account_index, folder_name, remote_path):
    account = get_account(account_index)
    if not account:
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_ACCOUNT_NOT_FOUND, xbmcgui.NOTIFICATION_ERROR)
        return

    download_root = get_download_path()
    if not download_root:
        return

    remote_path = normalize_collection_path(remote_path)
    if not remote_path:
        return

    info = resolve_media_info(folder_name, load_overrides())
    folder, jobs = _plan_downloads(account, info, remote_path, download_root)

    if not jobs:
        xbmcgui.Dialog().ok(APP_NAME, DIALOG_DOWNLOAD_NO_VIDEOS.format(info['title']))
        return

    total_size = sum(item.get('size') or 0 for item, _ in jobs)
    if not xbmcgui.Dialog().yesno(
        APP_NAME, DIALOG_DOWNLOAD_CONFIRM.format(len(jobs), _format_size(total_size), info['title'])
    ):
        return

    _ensure_folder(folder)
    if info['media_type'] == 'movie':
        write_movie_nfo(folder, info['title'], info['year'], info['tmdb_id'], info['imdb_id'])
    else:
        write_tvshow_nfo(folder, info['title'], info['tvdb_id'], info['tmdb_id'], info['imdb_id'])

    # Background progress: the transfer can take a long time and must not block the Kodi UI.
    progress = xbmcgui.DialogProgressBG()
    progress.create(PROGRESS_DOWNLOAD_TITLE.format(APP_NAME), info['title'])

    downloaded = skipped = failed = 0
    try:
        for index, (item, dest_path) in enumerate(jobs, start=1):
            file_label = os.path.basename(dest_path)
            expected_size = item.get('size') or 0
            if expected_size and _existing_size(dest_path) == expected_size:
                skipped += 1
                continue

            def on_progress(written, total, index=index, file_label=file_label):
                file_pct = float(written) / total if total else 0
                overall = int(((index - 1) + file_pct) * 100 / len(jobs))
                progress.update(
                    overall,
                    message='{} ({} / {})'.format(
                        PROGRESS_DOWNLOAD_FILE.format(index, len(jobs), file_label),
                        _format_size(written),
                        _format_size(total),
                    ),
                )

            log('Downloading {} -> {}'.format(item['full_url'], dest_path))
            if _download_file(account, item, dest_path, on_progress):
                downloaded += 1
            else:
                failed += 1
    except DownloadCancelled:
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_DOWNLOAD_CANCELLED, xbmcgui.NOTIFICATION_WARNING)
        return
    finally:
        progress.close()

    subs_saved = _download_subtitles(folder, info['subs'])

    xbmcgui.Dialog().ok(APP_NAME, DIALOG_DOWNLOAD_DONE.format(downloaded, skipped, failed, subs_saved))
