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
LITTERBOX_UPLOAD_URL = "https://litterbox.catbox.moe/resources/internals/api.php"

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


def _build_multipart_body_with_fields(file_path: str, fields) -> tuple[bytes, str]:
    """Build multipart/form-data body with caller-provided form fields."""
    boundary = uuid.uuid4().hex
    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    parts = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="fileToUpload"; filename="{filename}"\r\n'.encode())
    parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())

    body = b"".join(parts)
    content_type_header = f"multipart/form-data; boundary={boundary}"
    return body, content_type_header


def _upload_and_verify(upload_url: str, file_path: str, fields, allowed_prefixes: tuple[str, ...]) -> str:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(file_path)

    body, content_type_header = _build_multipart_body_with_fields(file_path, fields)
    request = Request(
        upload_url,
        data=body,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": content_type_header,
        },
    )

    with urlopen(request, timeout=30) as response:
        url = response.read().decode("utf-8").strip()

    if not any(url.startswith(prefix) for prefix in allowed_prefixes):
        raise RuntimeError(f"Unexpected upload response: {url}")

    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=30) as response:
        uploaded = response.read()
    if not uploaded:
        raise RuntimeError("Upload returned an empty file")

    return url


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
    return _upload_and_verify(
        UPLOAD_URL,
        file_path,
        {"reqtype": "fileupload"},
        ("https://files.catbox.moe/",),
    )


def paste_file_litterbox(file_path: str, expiry: str = "72h") -> str:
    """Upload a local file to Litterbox and return the short URL."""
    return _upload_and_verify(
        LITTERBOX_UPLOAD_URL,
        file_path,
        {"reqtype": "fileupload", "time": expiry},
        ("https://litter.catbox.moe/",),
    )


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

    provider = "Catbox"
    try:
        url = paste_file(file_path)
    except Exception as first_exc:
        # Catbox can occasionally accept a request but serve an empty object;
        # retry once before falling back to Litterbox.
        try:
            url = paste_file(file_path)
        except Exception as second_exc:
            try:
                provider = "Litterbox"
                url = paste_file_litterbox(file_path)
            except Exception as third_exc:
                xbmc.log(
                    "[plugin.video.torbox] Export upload failed. "
                    f"Catbox attempt 1: {first_exc} | Catbox attempt 2: {second_exc} | "
                    f"Litterbox: {third_exc}",
                    xbmc.LOGERROR,
                )
                dialog = xbmcgui.Dialog()
                dialog.ok(
                    "Export Failed",
                    "Could not upload overrides file.\n\n"
                    "Catbox attempt 1:\n{}\n\nCatbox attempt 2:\n{}\n\n"
                    "Litterbox fallback:\n{}".format(first_exc, second_exc, third_exc),
                )
                return ""

    dialog = xbmcgui.Dialog()
    dialog.textviewer(
        "Config uploaded",
        f"Uploaded via {provider}.\n"
        f"Paste this URL into your GitHub workflow input:\n\n{url}",
    )
    return url