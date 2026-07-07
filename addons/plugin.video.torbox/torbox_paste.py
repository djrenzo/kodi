"""
Uploads a local text/JSON file to 0x0.st (https://0x0.st), an anonymous
file-paste service that needs no API key or token, and returns the short
URL it hands back. That URL can be curled directly (it serves the raw file
content, not an HTML page), so it's ready to hand to a GitHub workflow
as a `workflow_dispatch` input.

0x0.st specifics worth knowing:
- No auth required, but it DOES require a descriptive User-Agent or it
  will reject the request (403) as abuse prevention. Set USER_AGENT below
  to something identifying your addon (name + a contact/repo URL).
- Retention is size-based: small files (like a config/JSON) get the
  minimum retention, currently 30 days - plenty of time for a workflow
  to pick it up shortly after you generate the link.
- The returned URL is short (e.g. https://0x0.st/abcd.json) and serves
  the raw file directly, so `curl -sL <url>` gets you the file contents.
"""

import mimetypes
import os
import uuid
from urllib.request import Request, urlopen

PASTE_URL = "https://0x0.st"

# Customize this - 0x0.st blocks generic/missing User-Agents.
USER_AGENT = "kodi-addon-config-sync/1.0 (+https://github.com/yourname/yourrepo)"


def _build_multipart_body(file_path: str) -> tuple[bytes, str]:
    """Manually build a multipart/form-data body (stdlib only, no requests)."""
    boundary = uuid.uuid4().hex
    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    )
    parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())

    body = b"".join(parts)
    content_type_header = f"multipart/form-data; boundary={boundary}"
    return body, content_type_header


def paste_file(file_path: str) -> str:
    """
    Upload a local file to 0x0.st and return the short URL to it.

    Args:
        file_path: Path to the local text/JSON file (e.g. somewhere under
                    the Kodi addon's data directory).

    Returns:
        The short URL (str) that serves the raw file content, e.g.
        "https://0x0.st/abcd.json"

    Raises:
        FileNotFoundError: if file_path doesn't exist.
        urllib.error.HTTPError: if the upload is rejected (e.g. missing/
                                 blocked User-Agent, file too large, or
                                 the service is rate-limiting you).
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(file_path)

    body, content_type_header = _build_multipart_body(file_path)

    request = Request(
        PASTE_URL,
        data=body,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": content_type_header,
        },
    )

    with urlopen(request, timeout=30) as response:
        url = response.read().decode("utf-8").strip()

    return url


# --- Optional Kodi-specific wrapper -----------------------------------
# Only import Kodi modules when actually running inside Kodi, so this
# file can still be imported/tested outside the addon environment.
def paste_and_show_dialog(file_path: str) -> str:
    """
    Upload file_path and display the resulting URL in a Kodi dialog the
    user can select and copy (Kodi has no reliable cross-platform
    clipboard-write API, so a copyable text dialog is the practical option).
    """
    import xbmcgui  # noqa: local import, Kodi-only

    url = paste_file(file_path)

    dialog = xbmcgui.Dialog()
    dialog.textviewer(
        "Config uploaded",
        f"Paste this URL into your GitHub workflow input:\n\n{url}",
    )
    return url