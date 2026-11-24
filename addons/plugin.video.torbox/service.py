"""Background service: runs the local streaming proxy for as long as Kodi is up, and
keeps the Supabase project awake."""

import threading
import traceback

import xbmc

from torbox_proxy import StreamProxy

PING_DELAY = 30             # seconds after startup, so the network is up
PING_INTERVAL = 24 * 3600   # Kodi boxes can run for weeks without a restart


def _log(message, level=xbmc.LOGINFO):
    xbmc.log('[plugin.video.torbox] [supabase] {}'.format(message), level)


def _ping_supabase():
    # Imported here so a Supabase problem can never stop the proxy from starting.
    from torbox_supabase import SupabaseClient, SupabaseError, is_configured
    if not is_configured():
        return
    try:
        SupabaseClient().ping()
        _log('Keep-alive ping OK')
    except SupabaseError as exc:
        _log('Keep-alive ping failed: {} (if the project is paused, restore it in the '
             'Supabase dashboard)'.format(exc), xbmc.LOGWARNING)


def _keep_alive():
    """Free Supabase projects pause after 7 days without activity."""
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(PING_DELAY):
        return
    while True:
        try:
            _ping_supabase()
        except Exception as exc:
            _log('Keep-alive ping crashed: {}\n{}'.format(exc, traceback.format_exc()), xbmc.LOGERROR)
        if monitor.waitForAbort(PING_INTERVAL):
            return


def run():
    monitor = xbmc.Monitor()
    threading.Thread(target=_keep_alive, name='torbox-supabase-ping', daemon=True).start()

    proxy = StreamProxy()
    if not proxy.start():
        xbmc.log('[plugin.video.torbox] [proxy] Could not start; playing streams directly', xbmc.LOGERROR)
        monitor.waitForAbort()
        return
    try:
        monitor.waitForAbort()
    finally:
        proxy.stop()


if __name__ == '__main__':
    run()
