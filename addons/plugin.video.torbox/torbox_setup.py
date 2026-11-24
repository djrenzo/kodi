import threading
import time
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

import xbmcgui

from torbox_common import ADDON, APP_NAME, save_credentials
from torbox_text import (
    DIALOG_SETUP_SCAN_PROVIDERS_LABEL,
    DIALOG_SETUP_SCAN_LABEL,
    DIALOG_SETUP_SCAN_SUPABASE_LABEL,
    NOTIFY_INVALID_ACCOUNT_SLOT,
    PROVIDERS_SETUP_PAGE_HTML,
    SETUP_PAGE_HTML,
    SETUP_RESULT_ERROR_HTML,
    SETUP_RESULT_OK_HTML,
    SUPABASE_SETUP_PAGE_HTML,
)

_server = None
_server_account_id = None
_server_mode = 'account'
_server_port = 8765
_qr_window = None


def _get_prefill_settings(account_id):
    return {
        'url': ADDON.getSettingString('account{}_url'.format(account_id)),
        'username': ADDON.getSettingString('account{}_username'.format(account_id)),
    }


def _get_provider_prefill_settings():
    return {
        'aiostreams_url': ADDON.getSettingString('aiostreams_url'),
        'tmdb_key': ADDON.getSettingString('tmdb_key'),
        'wyzie_key': ADDON.getSettingString('wyzie_key'),
    }


def _supabase_form_error(form):
    """Validate and save the Supabase form; returns an error message or None."""
    url = form.get('supabase_url', [''])[0].strip().rstrip('/')
    key = form.get('supabase_key', [''])[0].strip()
    email = form.get('supabase_email', [''])[0].strip()
    password = form.get('supabase_password', [''])[0]

    if not url or not key or not email:
        return 'Please go back and fill in the project URL, key and email.'
    if not url.startswith('https://'):
        return 'The project URL must start with https:// (e.g. https://abcdefgh.supabase.co).'
    if key.startswith('sb_secret_') or '"service_role"' in _jwt_payload(key):
        return 'That is the secret (service_role) key. Use the publishable/anon key instead.'
    if not password and not ADDON.getSettingString('supabase_password'):
        return 'Please go back and enter the password.'

    ADDON.setSettingString('supabase_url', url)
    ADDON.setSettingString('supabase_key', key)
    ADDON.setSettingString('supabase_email', email)
    if password:
        ADDON.setSettingString('supabase_password', password)
    return None


def _jwt_payload(token):
    """Decoded payload of a legacy JWT key ('' when it isn't one)."""
    import base64

    parts = token.split('.')
    if len(parts) != 3:
        return ''
    try:
        return base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)).decode('utf-8', 'replace')
    except Exception:
        return ''


def _is_valid_aiostreams_template(value):
    template = (value or '').strip()
    if not template:
        return False

    if not (template.startswith('http://') or template.startswith('https://')):
        return False

    if '{media_type}' not in template or '{imdb_id}' not in template:
        return False

    return True


class ConfigHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        del format, args
        return

    def do_GET(self):
        try:
            if _server_mode == 'supabase':
                html = SUPABASE_SETUP_PAGE_HTML.format(
                    app_name=APP_NAME,
                    url_value=escape(ADDON.getSettingString('supabase_url'), quote=True),
                    key_value=escape(ADDON.getSettingString('supabase_key'), quote=True),
                    email_value=escape(ADDON.getSettingString('supabase_email'), quote=True),
                )
            elif _server_mode == 'providers':
                prefill = _get_provider_prefill_settings()
                html = PROVIDERS_SETUP_PAGE_HTML.format(
                    app_name=APP_NAME,
                    aiostreams_value=escape(prefill.get('aiostreams_url', ''), quote=True),
                    tmdb_key_value=escape(prefill.get('tmdb_key', ''), quote=True),
                    wyzie_key_value=escape(prefill.get('wyzie_key', ''), quote=True),
                )
            else:
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
        except Exception as exc:
            self.send_response(500)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(
                SETUP_RESULT_ERROR_HTML.format(
                    app_name=APP_NAME,
                    error_message='Failed to render setup page: {}'.format(exc),
                ).encode('utf-8')
            )

    def do_POST(self):
        global _qr_window
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0:
                self.send_response(400)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(
                    SETUP_RESULT_ERROR_HTML.format(
                        app_name=APP_NAME,
                        error_message='Missing form data.',
                    ).encode('utf-8')
                )
                return

            data = self.rfile.read(length).decode('utf-8')
            form = parse_qs(data)

            if _server_mode == 'supabase':
                error = _supabase_form_error(form)
                if error:
                    self.send_response(400)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(
                        SETUP_RESULT_ERROR_HTML.format(app_name=APP_NAME, error_message=escape(error)).encode('utf-8')
                    )
                    return
            elif _server_mode == 'providers':
                aiostreams_url = form.get('aiostreams_url', [''])[0].strip()
                tmdb_key = form.get('tmdb_key', [''])[0].strip()
                wyzie_key = form.get('wyzie_key', [''])[0].strip()

                if not aiostreams_url or not tmdb_key or not wyzie_key:
                    self.send_response(400)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(
                        SETUP_RESULT_ERROR_HTML.format(
                            app_name=APP_NAME,
                            error_message='Please go back and complete all provider fields before saving.',
                        ).encode('utf-8')
                    )
                    return

                if not _is_valid_aiostreams_template(aiostreams_url):
                    self.send_response(400)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(
                        SETUP_RESULT_ERROR_HTML.format(
                            app_name=APP_NAME,
                            error_message='AIOStreams URL must start with http(s) and include {media_type} and {imdb_id}.',
                        ).encode('utf-8')
                    )
                    return

                ADDON.setSettingString('aiostreams_url', aiostreams_url)
                ADDON.setSettingString('tmdb_key', tmdb_key)
                ADDON.setSettingString('wyzie_key', wyzie_key)
            else:
                url = form.get('url', [''])[0]
                username = form.get('username', [''])[0]
                password = form.get('password', [''])[0]

                if not url.strip() or not username.strip() or not password:
                    self.send_response(400)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(
                        SETUP_RESULT_ERROR_HTML.format(
                            app_name=APP_NAME,
                            error_message='Please go back and complete all fields before saving.',
                        ).encode('utf-8')
                    )
                    return

                save_credentials(_server_account_id, url.strip(), username.strip(), password)

            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(SETUP_RESULT_OK_HTML.format(app_name=APP_NAME).encode('utf-8'))

            threading.Thread(target=_server.shutdown, daemon=True).start()

            if _qr_window is not None:
                _qr_window.close()
        except Exception as exc:
            self.send_response(500)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(
                SETUP_RESULT_ERROR_HTML.format(
                    app_name=APP_NAME,
                    error_message='Failed to process setup form: {}'.format(exc),
                ).encode('utf-8')
            )


def _start_setup_server(account_id=None, mode='account', port=8765):
    global _server
    global _server_account_id
    global _server_mode
    global _server_port

    if _server is not None:
        try:
            _server.shutdown()
            _server.server_close()
        except Exception:
            pass

    _server_account_id = account_id
    _server_mode = mode
    _server_port = int(port)
    _server = HTTPServer(('0.0.0.0', _server_port), ConfigHandler)
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
    def __init__(self, setup_url, label):
        super().__init__()

        qr_url = (
            'https://api.qrserver.com/v1/create-qr-code/'
            '?size=400x400&data={}&t={}'.format(setup_url, int(time.time()))
        )

        self.qr = xbmcgui.ControlImage(200, 75, 400, 400, qr_url)
        self.label = xbmcgui.ControlLabel(
            150,
            490,
            500,
            30,
            label,
            alignment=2,
        )

        self.url_label = xbmcgui.ControlLabel(
            100,
            525,
            600,
            30,
            'Open in browser: {}'.format(setup_url),
            alignment=2,
        )

        self.addControl(self.qr)
        self.addControl(self.label)
        self.addControl(self.url_label)

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()


def add_account(account_id):
    global _qr_window

    if account_id < 1:
        xbmcgui.Dialog().notification(APP_NAME, NOTIFY_INVALID_ACCOUNT_SLOT, xbmcgui.NOTIFICATION_ERROR)
        return

    _start_setup_server(account_id=account_id, mode='account', port=8765)
    ip = _get_local_ip()
    setup_url = 'http://{}:8765'.format(ip)

    dialog = QRDialog(setup_url, DIALOG_SETUP_SCAN_LABEL.format(APP_NAME))
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


def configure_providers():
    global _qr_window

    _start_setup_server(mode='providers', port=8766)
    ip = _get_local_ip()
    setup_url = 'http://{}:8766'.format(ip)

    dialog = QRDialog(setup_url, DIALOG_SETUP_SCAN_PROVIDERS_LABEL.format(APP_NAME))
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


def configure_supabase():
    global _qr_window

    _start_setup_server(mode='supabase', port=8767)
    ip = _get_local_ip()
    setup_url = 'http://{}:8767'.format(ip)

    dialog = QRDialog(setup_url, DIALOG_SETUP_SCAN_SUPABASE_LABEL.format(APP_NAME))
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
