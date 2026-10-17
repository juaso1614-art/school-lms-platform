"""KNEC practical archive (``.knec``) validation helpers.

A ``.knec`` submission is a ZIP container named
``[IndexNumber]_[SubjectCode].knec`` with the payload structure:

    ├── manifest.json        # candidate metadata + payload inventory
    ├── signature.sig        # hex HMAC-SHA256 tag over manifest.json bytes
    ├── data/
    │   ├── readings.csv
    │   ├── lab_state.json
    │   └── report.pdf
    └── media/
        ├── setup_photo.jpg
        └── process_proof.webm

The browser packer (``static/knec-packer.js``) builds the archive with
fflate and signs ``manifest.json`` with an HMAC-SHA256 key derived from
the server secret (``signing_key``) and served to the submission page;
``views.knec_submit`` re-validates the archive server side: structure,
filename, manifest inventory, SHA-256 payload digests and the HMAC
signature.
"""

import hashlib
import hmac
import json
import re
import zipfile
from functools import lru_cache
from io import BytesIO

from django.conf import settings

ARCHIVE_EXTENSION = ".knec"
MANIFEST_ENTRY = "manifest.json"
SIGNATURE_ENTRY = "signature.sig"
REQUIRED_ENTRIES = (
    MANIFEST_ENTRY,
    SIGNATURE_ENTRY,
    "data/readings.csv",
    "data/lab_state.json",
    "data/report.pdf",
)
MEDIA_PREFIX = "media/"
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024  # 100 MB

ARCHIVE_NAME_RE = re.compile(r"^(?P<index>\d{1,12})_(?P<code>232|233|231|451)\.knec$")

SUBJECTS = {
    "232": {"name": "Physics", "paper": "3"},
    "233": {"name": "Chemistry", "paper": "3"},
    "231": {"name": "Biology", "paper": "3"},
    "451": {"name": "Computer Studies", "paper": "2"},
}


@lru_cache(maxsize=1)
def signing_key() -> str:
    """HMAC-SHA256 key shared with the browser packer for the exam session."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        b"knec-practical-archive-v1",
        hashlib.sha256,
    ).hexdigest()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _signature(manifest_bytes: bytes, hmac_key_hex: str) -> str:
    return hmac.new(
        hmac_key_hex.encode("utf-8"), manifest_bytes, hashlib.sha256
    ).hexdigest()


def validate_archive(archive_bytes: bytes, filename: str):
    """Validate a ``.knec`` archive.

    Returns ``(manifest_or_none, errors)``; ``manifest`` is only set when
    every check passed. The signature is verified against the server
    signing key the browser packer signed the manifest with.
    """
    errors = []
    manifest = None

    if not filename.lower().endswith(ARCHIVE_EXTENSION):
        errors.append("Archive must use the .knec extension.")
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        errors.append("Archive exceeds the 100 MB limit.")
    if errors:
        return None, errors

    name_match = ARCHIVE_NAME_RE.match(filename)
    if not name_match:
        errors.append(
            "Archive name must follow [IndexNumber]_[SubjectCode].knec "
            "with subject code 232, 233, 231 or 451."
        )

    try:
        with zipfile.ZipFile(BytesIO(archive_bytes)) as zf:
            names = set(zf.namelist())
            missing = [entry for entry in REQUIRED_ENTRIES if entry not in names]
            if missing:
                errors.append(f"Missing required archive entries: {', '.join(missing)}.")
            if errors:
                return None, errors

            manifest_bytes = zf.read(MANIFEST_ENTRY)
            signature_hex = zf.read(SIGNATURE_ENTRY).decode("ascii", "strict").strip()

            if not hmac.compare_digest(signature_hex, _signature(manifest_bytes, hmac_key_hex)):
                errors.append("Signature verification failed — the archive is not trustworthy.")
                return None, errors

            manifest = json.loads(manifest_bytes.decode("utf-8"))
            candidate = manifest.get("candidate") or {}
            subject = manifest.get("subject") or {}
            inventory = manifest.get("payload") or []

            if str(candidate.get("index_number", "")) != name_match.group("index"):
                errors.append("Manifest index number does not match the archive filename.")
            if str(subject.get("code", "")) != name_match.group("code"):
                errors.append("Manifest subject code does not match the archive filename.")
            expected_paper = SUBJECTS[name_match.group("code")]["paper"]
            if str(subject.get("paper", "")) != expected_paper:
                errors.append(f"Unexpected paper number; expected {expected_paper}.")

            for entry in inventory:
                name = entry.get("name", "")
                if name not in names:
                    errors.append(f"Listed payload '{name}' is not in the archive.")
                    continue
                data = zf.read(name)
                if entry.get("size") != len(data):
                    errors.append(f"Payload '{name}' size does not match the manifest.")
                if entry.get("sha256") and not hmac.compare_digest(
                    entry["sha256"], _sha256_hex(data)
                ):
                    errors.append(f"Payload '{name}' SHA-256 digest does not match the manifest.")
            for name in names:
                if name.startswith(MEDIA_PREFIX) and not name.endswith("/"):
                    inventory_names = {entry.get("name") for entry in inventory}
                    if name not in inventory_names:
                        errors.append(f"Media file '{name}' is not listed in the manifest.")
    except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
        errors.append(f"Archive could not be read as a valid .knec submission ({exc}).")

    if errors:
        return None, errors
    return manifest, []
