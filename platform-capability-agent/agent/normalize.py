"""
Capability-name normalization.

The knowledge base defines an open vocabulary of capability IDs (snake_case,
defined in the markdown files themselves — there is no hardcoded master enum).
This module only does two things:

1. Turns free-text input ("Document Upload", "document-upload") into the same
   snake_case form used as keys in the knowledge base ("document_upload").
2. Resolves a small set of known aliases/synonyms to their canonical ID, so a
   caller typing "auth" or "file upload" still matches.

If a capability isn't in the alias table, its normalized form is used as-is. This
keeps the system extensible: adding a new capability to a platform's markdown file
does not require touching this code.
"""

from __future__ import annotations

import re

_ALIASES = {
    "auth": "authentication",
    "authenticate": "authentication",
    "login": "authentication",
    "otp": "otp_verification",
    "form": "form_input",
    "forms": "form_input",
    "file_upload": "document_upload",
    "upload": "document_upload",
    "attachment": "document_upload",
    "api": "api_action",
    "api_call": "api_action",
    "backend_call": "api_action",
    "camera": "native_camera_capture",
    "camera_capture": "native_camera_capture",
    "gps": "geolocation_capture",
    "location": "geolocation_capture",
    "geolocation": "geolocation_capture",
    "voice": "voice_input",
    "speech_input": "voice_input",
    "keypad_input": "dtmf_input",
    "dtmf": "dtmf_input",
    "push_notification": "push_notification_trigger",
    "notification": "push_notification_trigger",
    "offline": "offline_mode",
    "status": "status_tracking",
    "status_update": "status_tracking",
}


def normalize_capability(raw: str) -> str:
    """Normalize a free-text capability name to its canonical snake_case ID."""
    slug = raw.strip().lower()
    slug = re.sub(r"[\s\-]+", "_", slug)
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return _ALIASES.get(slug, slug)


def normalize_platform(raw: str) -> str:
    """Normalize a platform name for case/whitespace-insensitive lookup."""
    return re.sub(r"[\s\-]+", "_", raw.strip()).upper()
