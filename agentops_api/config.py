"""AgentOps API settings."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from hdfc_journey.config import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("AGENTOPS_DATA_DIR", REPO_ROOT / "agentops_data"))
DB_PATH = Path(os.environ.get("AGENTOPS_DB_PATH", DATA_DIR / "agentops.sqlite3"))
UPLOAD_DIR = Path(os.environ.get("AGENTOPS_UPLOAD_DIR", DATA_DIR / "uploads"))
KNOWLEDGE_ROOT = REPO_ROOT / "Knowledge_Base"
SECRET_KEY = os.environ.get("AGENTOPS_SECRET_KEY") or secrets.token_hex(32)
SESSION_HOURS = int(os.environ.get("AGENTOPS_SESSION_HOURS", "12"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "AGENTOPS_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
    ).split(",")
    if origin.strip()
]
BOOT_ID = secrets.token_hex(8)

SEED_USERS = (
    {
        "username": os.environ.get("AGENTOPS_ADMIN_USER", "admin"),
        "password": os.environ.get("AGENTOPS_ADMIN_PASSWORD", "ChangeMeAdmin!1"),
        "role": "super_admin",
        "display_name": "Platform Super Admin",
    },
    {
        "username": os.environ.get("AGENTOPS_APPROVER_USER", "approver"),
        "password": os.environ.get("AGENTOPS_APPROVER_PASSWORD", "ChangeMeApprover!1"),
        "role": "approver",
        "display_name": "Journey Approver",
    },
    {
        "username": os.environ.get("AGENTOPS_VIEWER_USER", "viewer"),
        "password": os.environ.get("AGENTOPS_VIEWER_PASSWORD", "ChangeMeViewer!1"),
        "role": "viewer",
        "display_name": "Operations Viewer",
    },
)
