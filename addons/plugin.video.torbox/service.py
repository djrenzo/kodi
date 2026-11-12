"""Background service: runs the local streaming proxy for as long as Kodi is up."""

import xbmc

from torbox_proxy import StreamProxy


def run():
    proxy = StreamProxy()
    if not proxy.start():
        xbmc.log('[plugin.video.torbox] [proxy] Could not start; playing streams directly', xbmc.LOGERROR)
        return
    try:
        xbmc.Monitor().waitForAbort()
    finally:
        proxy.stop()


if __name__ == '__main__':
    run()
