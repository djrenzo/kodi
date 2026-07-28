"""User-facing strings for easier localization and consistency."""

MENU_ACCOUNT_BROWSE = '[B]{} - Browse[/B]'
MENU_ACCOUNT_EXPORT = '{} - Export Library'
MENU_ADD_ACCOUNT = '[COLOR springgreen]Add account {} via Phone[/COLOR]'
MENU_TOP_MOVIES = '[COLOR springgreen]Top Movies[/COLOR]'
MENU_TOP_SERIES = '[COLOR springgreen]Top Series[/COLOR]'
MENU_SEARCH = '[COLOR springgreen]Search[/COLOR]'
MENU_MANAGE_OVERRIDES = '[COLOR yellow]Manage show overrides[/COLOR]'
MENU_EXPORT_OVERRIDES = '[COLOR yellow]Export overrides[/COLOR]'
MENU_IMPORT_OVERRIDES = '[COLOR yellow]Import overrides[/COLOR]'
MENU_SETTINGS = '[COLOR gray]Settings[/COLOR]'

CONTEXT_SET_OVERRIDE = 'Set show title/override'
CONTEXT_ADD_SUBTITLES = 'Add subtitles'
CONTEXT_REFRESH_LIBRARY = 'Refresh library'
CONTEXT_EXPORT_SINGLE_ITEM = 'Export this item to library'

LABEL_MEDIA_UNKNOWN = '[COLOR red]{} |[/COLOR] {}'
LABEL_MEDIA_FOLDER = '[COLOR springgreen]{} |[/COLOR] {}'
LABEL_GRAY_ITEM = '[COLOR gray]{}[/COLOR]'

NOTIFY_ACCOUNT_NOT_FOUND = 'Account not found'
NOTIFY_OVERRIDE_SAVED = 'Override saved: "{}" [{}]'
NOTIFY_OVERRIDE_REMOVED = 'Override removed'
NOTIFY_SEARCHING_TMDB = 'Searching TMDB...'
NOTIFY_SEARCHING_SUBS = 'Searching subtitles...'
NOTIFY_SUBTITLE_SAVED = 'Subtitle saved: {}'
NOTIFY_INVALID_ACCOUNT_SLOT = 'Invalid account slot'
NOTIFY_CONNECTION_FAILED = 'Connection failed'
NOTIFY_HTTP_ERROR = 'HTTP Error {}'

DIALOG_OVERRIDES_TITLE = '{} Overrides'
DIALOG_OVERRIDES_SELECT_DELETE = '{} Overrides - select to delete'
DIALOG_OVERRIDES_EMPTY = (
    'No overrides configured yet.\n\n'
    'Long-press a show in the library view and choose "Set show override".'
)
DIALOG_OVERRIDES_DELETE_TITLE = 'Delete override?'
DIALOG_OVERRIDES_DELETE_BODY = 'Remove override for "{}"?'

DIALOG_SET_TITLE = 'Show/movie title for:\n"{}"'
DIALOG_SET_YEAR = 'Year (leave blank if unknown)'
DIALOG_SET_CONTENT_TYPE = 'Content type for "{}"'
DIALOG_SET_TVDB = 'TheTVDB ID (thetvdb.com - leave blank to auto)'
DIALOG_SET_TMDB = 'TMDB ID (themoviedb.org - leave blank to auto)'
DIALOG_PICK_TMDB = 'Choose TMDB match for "{}"'
DIALOG_MANUAL_TMDB = 'Enter TMDB ID manually'

DIALOG_SUBS_EXISTING = 'Existing subtitles'
DIALOG_SUBS_ADD_TITLE = '{} - Add Subtitles'
DIALOG_SUBS_NEED_TMDB = (
    'No TMDB ID is set for this title.\n\n'
    'Long-press the folder and choose "Set show title/override",\n'
    'then search TMDB and set the TMDB ID first.'
)
DIALOG_SUBS_NOT_FOUND = 'No subtitles found for TMDB ID {}.'
DIALOG_SUBS_PICK = 'Choose subtitle'
DIALOG_SUBS_LANGUAGE = 'Subtitle language'
DIALOG_SUBS_LANG_EN = 'English (en)'
DIALOG_SUBS_LANG_ES = 'Spanish (es)'
DIALOG_SUBS_LANG_SP = 'Spanish (sp)'
DIALOG_SUBS_PICK_VIDEO = 'Choose video file'
DIALOG_SUBS_NO_VIDEO_FILES = 'No video files found in this library folder.'
DIALOG_SUBS_BAD_RESULT = 'Subtitle result is missing a download URL.'
DIALOG_SUBS_DOWNLOAD_FAILED = 'Failed to download subtitle.\nCheck the log for details.'

DIALOG_LIBRARY_PATH_NOT_CONFIGURED = 'Library path not configured'
DIALOG_LIBRARY_EXPORT_DONE = 'Export complete\n\n{} STRM files generated'
DIALOG_LIBRARY_SOURCE_ADDED = (
    'TorBox Library source has been added.\n\n'
    'Go to Videos - Files - TorBox Library\n'
    'and set Content = TV Shows or Movies as appropriate.'
)
DIALOG_LIBRARY_SUBS_EXPORT_FIRST = 'Library path not configured. Export the library first.'

DIALOG_SETUP_SCAN_LABEL = 'Scan with your phone to add your {} account'

SETUP_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{app_name} Setup</title>
    <style>
        :root {{
            --bg-a: #ecf6ff;
            --bg-b: #edf9f5;
            --ink: #0f1f2e;
            --muted: #5f7386;
            --panel: #ffffff;
            --line: #d4e1ec;
            --brand-a: #005f88;
            --brand-b: #14a8a2;
            --brand-c: #0a7da8;
            --focus: rgba(10, 125, 168, 0.2);
            --shadow: 0 20px 48px rgba(17, 45, 68, 0.14);
        }}

        * {{ box-sizing: border-box; }}

        body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 24px;
            color: var(--ink);
            font-family: "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
            background:
                radial-gradient(1200px 540px at -15% 110%, #cfefff 0%, transparent 55%),
                radial-gradient(1100px 520px at 120% -30%, #cbf6ec 0%, transparent 58%),
                linear-gradient(160deg, var(--bg-a), var(--bg-b));
        }}

        .card {{
            width: 100%;
            max-width: 620px;
            border: 1px solid var(--line);
            border-radius: 18px;
            overflow: hidden;
            background: var(--panel);
            box-shadow: var(--shadow);
        }}

        .hero {{
            position: relative;
            padding: 24px;
            background: linear-gradient(135deg, var(--brand-a), var(--brand-b));
            color: #ffffff;
        }}

        .hero::after {{
            content: "";
            position: absolute;
            inset: 0;
            background: radial-gradient(500px 120px at 110% -20%, rgba(255,255,255,0.26), transparent 60%);
            pointer-events: none;
        }}

        .brand-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
        }}

        .logo {{
            width: 30px;
            height: 30px;
            border-radius: 9px;
            display: grid;
            place-items: center;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: .05em;
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.45);
            background: rgba(255, 255, 255, 0.2);
        }}

        .badge {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: .09em;
            opacity: .95;
        }}

        h1 {{
            margin: 0;
            font-size: 24px;
            line-height: 1.2;
            font-weight: 750;
        }}

        .main {{
            padding: 24px;
        }}

        .desc {{
            margin: 0 0 16px;
            line-height: 1.48;
            color: var(--muted);
            font-size: 14px;
        }}

        .info-list {{
            margin: 0 0 18px;
            padding: 0;
            list-style: none;
            display: grid;
            gap: 8px;
        }}

        .info-list li {{
            color: #234056;
            font-size: 13px;
        }}

        .info-list li::before {{
            content: "";
            width: 7px;
            height: 7px;
            margin-right: 8px;
            border-radius: 50%;
            display: inline-block;
            background: var(--brand-c);
            vertical-align: middle;
        }}

        form {{
            display: grid;
            gap: 13px;
        }}

        label {{
            display: grid;
            gap: 6px;
            font-size: 14px;
            font-weight: 640;
        }}

        input {{
            width: 100%;
            border-radius: 10px;
            border: 1px solid var(--line);
            background: #ffffff;
            color: var(--ink);
            font-size: 14px;
            padding: 12px 13px;
            outline: none;
            transition: border-color .16s ease, box-shadow .16s ease;
        }}

        input:focus {{
            border-color: var(--brand-c);
            box-shadow: 0 0 0 3px var(--focus);
        }}

        .hint {{
            color: var(--muted);
            font-size: 12px;
        }}

        button {{
            margin-top: 4px;
            border: 0;
            border-radius: 10px;
            color: #ffffff;
            background: linear-gradient(135deg, var(--brand-a), var(--brand-b));
            padding: 12px 16px;
            font-size: 14px;
            font-weight: 700;
            letter-spacing: .02em;
            cursor: pointer;
            transition: filter .16s ease, transform .04s ease;
        }}

        button:hover {{ filter: brightness(1.05); }}
        button:active {{ transform: translateY(1px); }}

        .foot {{
            border-top: 1px solid var(--line);
            padding: 12px 24px 16px;
            color: var(--muted);
            font-size: 12px;
        }}

        @media (max-width: 560px) {{
            body {{ padding: 14px; }}
            .hero, .main {{ padding: 18px; }}
            h1 {{ font-size: 22px; }}
        }}
    </style>
</head>
<body>
    <main class="card">
        <header class="hero">
            <div class="brand-row">
                <div class="logo">TB</div>
                <span class="badge">{app_name} WebDAV</span>
            </div>
            <h1>Connect Account {account}</h1>
        </header>
        <section class="main">
            <p class="desc">Securely add your WebDAV credentials for this account. The values are stored in your local Kodi addon settings.</p>
            <ul class="info-list">
                <li>Use the full HTTPS WebDAV endpoint</li>
                <li>Credentials are applied to direct playback and browsing</li>
            </ul>
            <form method="POST" novalidate>
                <label>
                    WebDAV URL
                    <input name="url" type="url" value="{url_value}" placeholder="https://webdav.example.com" required>
                    <span class="hint">Example: https://webdav.torbox.app</span>
                </label>
                <label>
                    Username
                    <input name="username" type="text" value="{username_value}" autocomplete="username" required>
                </label>
                <label>
                    Password
                    <input name="password" type="password" autocomplete="current-password" required>
                </label>
                <button type="submit">Save Account</button>
            </form>
        </section>
        <div class="foot">After saving, return to Kodi to continue setup.</div>
    </main>
</body>
</html>
"""

SETUP_RESULT_OK_HTML = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{app_name} Setup</title>
    <style>
        body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 20px;
            background: linear-gradient(170deg, #eef8ff, #e8f7f1);
            font-family: "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
            color: #112536;
        }}
        .card {{
            width: 100%;
            max-width: 470px;
            border: 1px solid #cfe1ee;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 14px 32px rgba(17, 45, 68, 0.11);
            padding: 26px;
            text-align: center;
        }}
        .check {{
            width: 44px;
            height: 44px;
            margin: 0 auto 12px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            color: #ffffff;
            font-size: 24px;
            background: linear-gradient(135deg, #0f8cae, #17b09d);
        }}
        h2 {{ margin: 0 0 10px; font-size: 23px; }}
        p {{ margin: 0; color: #5e7386; line-height: 1.45; }}
    </style>
</head>
<body>
    <main class="card">
        <div class="check">\u2713</div>
        <h2>Saved</h2>
        <p>Your credentials were stored successfully. You can close this page and return to Kodi.</p>
    </main>
</body>
</html>
"""

SETUP_RESULT_ERROR_HTML = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{app_name} Setup</title>
    <style>
        body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 20px;
            background: linear-gradient(170deg, #fff5f3, #ffefec);
            font-family: "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
            color: #3b1d1a;
        }}
        .card {{
            width: 100%;
            max-width: 470px;
            border: 1px solid #f0c9c4;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 14px 30px rgba(84, 33, 27, 0.11);
            padding: 26px;
            text-align: center;
        }}
        .warn {{
            width: 44px;
            height: 44px;
            margin: 0 auto 12px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            color: #ffffff;
            font-size: 22px;
            background: linear-gradient(135deg, #c54d3f, #dc6a4d);
        }}
        h2 {{ margin: 0 0 10px; font-size: 23px; }}
        p {{ margin: 0; color: #7f524a; line-height: 1.45; }}
    </style>
</head>
<body>
    <main class="card">
        <div class="warn">!</div>
        <h2>Missing Form Data</h2>
        <p>Please go back and complete all fields before saving.</p>
    </main>
</body>
</html>
"""
