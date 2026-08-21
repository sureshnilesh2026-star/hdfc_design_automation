"""Isolate AgentOps SQLite from developer data during tests."""

from __future__ import annotations

import os
from pathlib import Path

TMP = Path(__file__).resolve().parent / "_agentops_tmp"
os.environ.setdefault("AGENTOPS_SECRET_KEY", "test-secret-key-not-for-production")
os.environ["AGENTOPS_DATA_DIR"] = str(TMP)
os.environ.setdefault("AGENTOPS_ADMIN_PASSWORD", "ChangeMeAdmin!1")
os.environ.setdefault("AGENTOPS_APPROVER_PASSWORD", "ChangeMeApprover!1")
os.environ.setdefault("AGENTOPS_VIEWER_PASSWORD", "ChangeMeViewer!1")
TMP.mkdir(exist_ok=True)
for leftover in TMP.glob("*"):
    if leftover.is_file():
        leftover.unlink()
