"""Loading and validation of local files sent as Tuskr result attachments.

Tuskr's bulk result endpoint accepts at most two attachments of 5 MB each, so
those limits are enforced here, before any request leaves the process, instead
of letting the API reject the call.

An MCP tool argument is model-controlled, so a plain file path would let a
prompt injection upload any readable file to Tuskr. Attachments are therefore
off unless TUSKR_ATTACHMENT_DIR names a directory, and only files that resolve
inside it are read.
"""

import mimetypes
import os
from pathlib import Path

ATTACHMENT_DIR_ENV = "TUSKR_ATTACHMENT_DIR"
MAX_ATTACHMENTS = 2
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024


def load_attachments(paths: list[str]) -> list[tuple[str, bytes, str]]:
    """Validate local file paths and return (filename, bytes, mimetype) tuples.

    Relative paths resolve against TUSKR_ATTACHMENT_DIR. Symlinks are resolved
    before the containment check, so a link inside the directory cannot point
    at a file outside it.
    """
    root_value = os.environ.get(ATTACHMENT_DIR_ENV)
    if not root_value:
        raise ValueError(
            f"Attachments are disabled. Set {ATTACHMENT_DIR_ENV} to the "
            "directory the server may read attachments from."
        )

    if len(paths) > MAX_ATTACHMENTS:
        raise ValueError(
            f"At most {MAX_ATTACHMENTS} attachments are allowed per call, "
            f"got {len(paths)}."
        )

    root = Path(root_value).resolve()
    files = []
    for raw in paths:
        path = (root / raw).resolve()

        if not path.is_relative_to(root):
            raise ValueError(
                f"Attachment '{raw}' is outside the allowed directory "
                f"({ATTACHMENT_DIR_ENV})."
            )
        if not path.is_file():
            raise ValueError(f"Attachment '{raw}' is not an existing file.")

        size = path.stat().st_size
        if size > MAX_ATTACHMENT_BYTES:
            raise ValueError(
                f"Attachment '{raw}' is {size} bytes; the limit is "
                f"{MAX_ATTACHMENT_BYTES} bytes (5 MB)."
            )

        mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        files.append((path.name, path.read_bytes(), mimetype))

    return files
