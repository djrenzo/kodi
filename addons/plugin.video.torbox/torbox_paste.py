"""
Uploads a local text/JSON file to catbox.moe, an anonymous file host that
needs no API key or token, and returns the short URL it hands back. That
URL can be curled directly (it serves the raw file content, not an HTML
page), so it's ready to hand to a GitHub workflow as a `workflow_dispatch`
input.

catbox.moe specifics worth knowing:
- No auth required for uploads - just omit the `userhash` field in the
  POST and it uploads anonymously. (A userhash only matters if you want
  to later manage/delete the file from an account, which we don't need
  here.)
- Files persist indefinitely (no expiry), unlike some paste services, so
  there's no race to beat before a workflow picks it up.
- Max file size is 200MB, far more than needed for a config/JSON file.
- Blocks a short list of file types (mainly executables) - plain
  text/JSON is fine.

(Note: 0x0.st, an older no-key paste service, has had reliability
problems recently, including reports of the service being down/
overwhelmed by bots - that's most likely the source of a 503 if you were
using it. catbox.moe is the more actively maintained alternative.)
"""

import mimetypes
import os
import uuid
from urllib.request import Request, urlopen

UPLOAD_URL = "https://catbox.moe/user/api.php"

# catbox.moe doesn't require a descriptive User-Agent the way 0x0.st did,
# but setting one is still good practice / easier to debug in logs.
USER_AGENT = "kodi-addon-config-sync/1.0"


def _build_multipart_body(file_path: str) -> tuple[bytes, str]:
    """Manually build a multipart/form-data body (stdlib only, no requests)."""
    boundary = uuid.uuid4().hex
    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    def field(name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode()

    parts = []
    # reqtype=fileupload tells catbox this is a file upload.
    parts.append(field("reqtype", "fileupload"))
    # No "userhash" field at all -> anonymous upload.
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="fileToUpload"; filename="{filename}"\r\n'.encode()
    )
    parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())

    body = b"".join(parts)
    content_type_header = f"multipart/form-data; boundary={boundary}"
    return body, content_type_header


def paste_file(file_path: str) -> str:
    """
    Upload a local file to catbox.moe and return the short URL to it.

    Args:
        file_path: Path to the local text/JSON file (e.g. somewhere under
                    the Kodi addon's data directory).

    Returns:
        The short URL (str) that serves the raw file content, e.g.
        "https://files.catbox.moe/abcd12.json"

    Raises:
        FileNotFoundError: if file_path doesn't exist.
        urllib.error.HTTPError: if the upload is rejected (e.g. file too
                                 large, blocked file type, or the service
                                 is having issues).
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(file_path)

    body, content_type_header = _build_multipart_body(file_path)

    request = Request(
        UPLOAD_URL,
        data=body,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": content_type_header,
        },
    )

    with urlopen(request, timeout=30) as response:
        url = response.read().decode("utf-8").strip()

    if not url.startswith("https://files.catbox.moe/"):
        raise RuntimeError(f"Unexpected Catbox response: {url}")

    # Verify that the uploaded URL serves non-empty content.
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=30) as response:
        uploaded = response.read()
    if not uploaded:
        raise RuntimeError("Catbox returned an empty upload")

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
    import xbmc
    import xbmcgui  # noqa: local import, Kodi-only

    try:
        url = paste_file(file_path)
    except Exception:
        # Catbox can occasionally accept a request but serve an empty object;
        # retry once before surfacing the error.
        try:
            url = paste_file(file_path)
        except Exception as exc:
            xbmc.log(f"[plugin.video.torbox] Export upload failed: {exc}", xbmc.LOGERROR)
            dialog = xbmcgui.Dialog()
            dialog.ok(
                "Export Failed",
                "Could not upload overrides file.\n\nError:\n{}".format(exc),
            )
            raise

    dialog = xbmcgui.Dialog()
    dialog.textviewer(
        "Config uploaded",
        f"Paste this URL into your GitHub workflow input:\n\n{url}",
    )
    return url