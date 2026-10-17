"""Jitsi Meet integration for live lesson rooms (no credentials required)."""

import secrets
import string


JITSI_BASE_URL = "https://meet.jit.si"
ROOM_ALPHABET = string.ascii_lowercase + string.digits


def is_configured():
    """Jitsi Meet rooms are created directly from a URL, so no credentials are needed."""
    return True


def create_meeting(title=""):
    """Build a public Jitsi Meet room URL for a live lesson."""
    slug = "".join(character for character in title.casefold() if character.isalnum())[:40]
    suffix = "".join(secrets.choice(ROOM_ALPHABET) for _ in range(6))
    room = f"peak-group-{slug}-{suffix}" if slug else f"peak-group-{suffix}"
    return {"join_url": f"{JITSI_BASE_URL}/{room}", "space_name": room}
