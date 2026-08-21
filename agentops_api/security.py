"""Password hashing, signed sessions, and RBAC helpers.

Passwords are stored as PBKDF2-HMAC-SHA256. Session tokens are HMAC-signed
JSON payloads — never plaintext credentials.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from agentops_api.config import SECRET_KEY, SESSION_HOURS

Role = Literal["super_admin", "approver", "viewer"]

PBKDF2_ITERATIONS = 210_000
SALT_BYTES = 16

ROLE_RANK = {"viewer": 1, "approver": 2, "super_admin": 3}

PERMISSIONS: dict[str, set[Role]] = {
    "dashboard.read": {"super_admin", "approver", "viewer"},
    "agents.read": {"super_admin", "approver", "viewer"},
    "executions.read": {"super_admin", "approver", "viewer"},
    "executions.create": {"super_admin", "approver"},
    "executions.retry": {"super_admin", "approver"},
    "executions.approve": {"super_admin", "approver"},
    "knowledge.read": {"super_admin", "approver", "viewer"},
    "knowledge.write": {"super_admin"},
    "health.read": {"super_admin", "approver", "viewer"},
    "audit.read": {"super_admin"},
    "users.manage": {"super_admin"},
    "admin.read": {"super_admin"},
}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def hash_password(password: str) -> str:
    if not password or len(password) < 10:
        raise ValueError("Password must be at least 10 characters")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64url(salt)}${_b64url(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iter_s, salt_s, digest_s = stored.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    try:
        iterations = int(iter_s)
        salt = _b64url_decode(salt_s)
        expected = _b64url_decode(digest_s)
    except (ValueError, OSError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def issue_session_token(*, user_id: int, username: str, role: Role) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=SESSION_HOURS)).timestamp()),
        "jti": secrets.token_hex(12),
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(SECRET_KEY.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url(signature)}"


def decode_session_token(token: str) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    body, _, signature = token.partition(".")
    expected = hmac.new(SECRET_KEY.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    try:
        given = _b64url_decode(signature)
    except (ValueError, OSError):
        return None
    if not hmac.compare_digest(expected, given):
        return None
    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, json.JSONDecodeError, OSError):
        return None
    if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
        return None
    return payload


def has_permission(role: str, permission: str) -> bool:
    allowed = PERMISSIONS.get(permission)
    if not allowed:
        return False
    return role in allowed
