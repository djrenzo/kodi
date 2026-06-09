import threading
import time
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

import xbmcgui

from torbox_common import ADDON, APP_NAME, save_credentials
from torbox_text import (
    DIALOG_SETUP_SCAN_LABEL,
    NOTIFY_INVALID_ACCOUNT_SLOT,
    SETUP_PAGE_HTML,
    SETUP_RESULT_ERROR_HTML,
    SETUP_RESULT_OK_HTML,
)

_server = None
_server_account_id = None
_qr_window = None


def _get_prefill_settings(account_id):
    return {
        'url': ADDON.getSettingString('account{}_url'.format(account_id)),
        'username': ADDON.getSettingString('account{}_username'.format(account_id)),
    }


class ConfigHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        del format, args
        return

    def do_GET(self):
        prefill = _get_prefill_settings(_server_account_id)
        html = SETUP_PAGE_HTML.format(
            app_name=APP_NAME,
            account=_server_account_id,
            url_value=escape(prefill.get('url', ''), quote=True),
            username_value=escape(prefill.get('username', ''), quote=True),
        )

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def do_POST(self):
        global _qr_window
        length = int(self.headers.get('Content-Length', '0'))
        if length <= 0:
            self.send_response(400)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(SETUP_RESULT_ERROR_HTML.format(app_name=APP_NAME).encode('utf-8'))
            return

        data = self.rfile.read(length).decode('utf-8')
        form = parse_qs(data)

        url = form.get('url', [''])[0]
        username = form.get('username', [''])[0]
        password = form.get('password', [''])[0]

        if not url.strip() or not username.strip() or not password:
            self.send_response(400)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(SETUP_RESULT_ERROR_HTML.format(app_name=APP_NAME).encode('utf-8'))
            return

        save_credentials(_server_account_id, url.strip(), username.strip(), password)

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(SETUP_RESULT_OK_HTML.format(app_name=APP_NAME).encode('utf-8'))

        threading.Thread(target=_server.shutdown, daemon=True).start()

        if _qr_window is not None:
            _qr_window.close()


def _start_setup_server(account_id):
    global _server
    global _server_account_id

    if _server is not None:
        try:
            _server.shutdown()
            _server.server_close()
        except Exception:
            pass

    _server_account_id = account_id
    _server = HTTPServer(('0.0.0.0', 8765), ConfigHandler)
    threading.Thread(target=_server.serve_forever, daemon=True).start()


def _get_local_ip():
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('8.8.8.8', 80))
        return sock.getsockname()[0]
    finally:
        sock.close()


class QRDialog(xbmcgui.WindowDialog):
    def __init__(self, ip):
        super().__init__()

        url = 'http://{}:8765'.format(ip)
        qr_url = (
            'https://api.qrserver.com/v1/create-qr-code/'
            '?size=400x400&data={}&t={}'.format(url, int(time.time()))
        )

        self.qr = xbmcgui.ControlImage(200, 75, 400, 400, qr_url)
        self.label = xbmcgui.ControlLabel(
            150,
            490,
            500,
            30,
            DIALOG_SETUP_SCAN_LABEL.format(APP_NAME),
            alignment=2,
        )

        self.addControl(self.qr)
        self.addControl(self.label)

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()


def add_account(account_id):
    global _qr_window

    if account_id < 1:
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_INVALID_ACCOUNT_SLOT, xbmcgui.NOTIFICATION_ERROR)
        return

    _start_setup_server(account_id)
    ip = _get_local_ip()

    dialog = QRDialog(ip)
    _qr_window = dialog

    dialog.doModal()

    del dialog
    _qr_window = None

    if _server is not None:
        try:
            _server.shutdown()
            _server.server_close()
        except Exception:
            pass
