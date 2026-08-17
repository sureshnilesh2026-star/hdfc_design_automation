#!/usr/bin/env python3
"""
CLI for the Platform Capability Agent.

Examples:

    python3 cli.py --platform EVA --requirements authentication,form_input,document_upload,api_action

    python3 cli.py --platform EVA \\
        --requirements "authentication, form input, document upload, api call, camera capture"

    python3 cli.py --platform WHATSAPP_BOT --requirements authentication
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import PlatformCapabilityAgent, CapabilityRequest  # noqa: E402

DEFAULT_KNOWLEDGE_DIR = str(Path(__file__).resolve().parent / "knowledge")


def main() -> None:
    parser = argparse.ArgumentParser(description="Platform Capability Agent")
    parser.add_argument("--platform", required=True, help="Platform name, e.g. EVA")
    parser.add_argument("--requirements", required=True,
                         help="Comma-separated list of required capabilities")
    parser.add_argument("--knowledge-dir", default=DEFAULT_KNOWLEDGE_DIR,
                         help="Directory of platform capability markdown files")
    parser.add_argument("--compact", action="store_true",
                         help="Print compact single-line JSON instead of pretty-printed (default: pretty)")
    args = parser.parse_args()

    requirements = [r.strip() for r in args.requirements.split(",") if r.strip()]

    agent = PlatformCapabilityAgent(knowledge_dir=args.knowledge_dir)
    response = agent.evaluate(CapabilityRequest(platform=args.platform,
                                                  required_capabilities=requirements))

    print(json.dumps(response.to_dict(), indent=None if args.compact else 2))


if __name__ == "__main__":
    main()
