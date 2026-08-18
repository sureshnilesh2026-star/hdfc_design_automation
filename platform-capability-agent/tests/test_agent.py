"""
Unit tests for the Platform Capability Agent.

Covers the six required scenarios from the brief:
  1. Platform supports everything requested.
  2. Platform supports only some requirements.
  3. Platform supports none of the requirements.
  4. Platform is unknown.
  5. Knowledge base does not contain enough information.
  6. Two knowledge documents contain conflicting information.

Run with:  python3 -m unittest discover -s tests -v
(run from the project root)
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import PlatformCapabilityAgent, CapabilityRequest, SupportStatus  # noqa: E402
from agent.knowledge_loader import load_knowledge_base  # noqa: E402

KNOWLEDGE_DIR = str(Path(__file__).resolve().parent.parent / "knowledge")


class PlatformCapabilityAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = PlatformCapabilityAgent(knowledge_dir=KNOWLEDGE_DIR)

    # 1. Full support -------------------------------------------------------

    def test_full_support(self):
        resp = self.agent.evaluate(CapabilityRequest(
            platform="EVA",
            required_capabilities=["authentication", "form_input", "document_upload", "api_action"],
        ))
        self.assertEqual(resp.status, SupportStatus.FULLY_SUPPORTED.value)
        self.assertTrue(resp.supported)
        self.assertEqual(set(resp.supported_capabilities),
                          {"authentication", "form_input", "document_upload", "api_action"})
        self.assertEqual(resp.unsupported_capabilities, [])
        self.assertEqual(resp.capabilities_needing_investigation, [])
        self.assertEqual(resp.conflicts, [])
        self.assertEqual(resp.confidence, 1.0)
        self.assertIn("eva-platform-capabilities.md", resp.knowledge_sources)

    # 2. Partial support ------------------------------------------------------

    def test_partial_support(self):
        resp = self.agent.evaluate(CapabilityRequest(
            platform="EVA",
            required_capabilities=[
                "authentication", "form input", "document upload", "api call", "camera capture",
            ],
        ))
        self.assertEqual(resp.status, SupportStatus.PARTIALLY_SUPPORTED.value)
        self.assertFalse(resp.supported)
        self.assertIn("native_camera_capture", resp.unsupported_capabilities)
        self.assertEqual(len(resp.supported_capabilities), 4)
        self.assertTrue(any("attachment component" in c for c in resp.constraints))

    # 3. No support -----------------------------------------------------------

    def test_no_support(self):
        resp = self.agent.evaluate(CapabilityRequest(
            platform="IVR",
            required_capabilities=["form_input", "document_upload", "native_camera_capture"],
        ))
        self.assertEqual(resp.status, SupportStatus.NOT_SUPPORTED.value)
        self.assertFalse(resp.supported)
        self.assertEqual(resp.supported_capabilities, [])
        self.assertEqual(set(resp.unsupported_capabilities),
                          {"form_input", "document_upload", "native_camera_capture"})
        # We're fully certain it's unsupported -- confidence should be high, not low.
        self.assertEqual(resp.confidence, 1.0)

    # 4. Unknown platform -------------------------------------------------------

    def test_unknown_platform(self):
        resp = self.agent.evaluate(CapabilityRequest(
            platform="WHATSAPP_BOT",
            required_capabilities=["authentication", "form_input"],
        ))
        self.assertEqual(resp.status, SupportStatus.UNKNOWN_PLATFORM.value)
        self.assertFalse(resp.supported)
        self.assertEqual(resp.confidence, 0.0)
        self.assertEqual(resp.knowledge_sources, [])
        self.assertEqual(set(resp.capabilities_needing_investigation),
                          {"authentication", "form_input"})

    # 5. Insufficient knowledge (capability not documented anywhere) ------------

    def test_insufficient_knowledge_undocumented_capability(self):
        resp = self.agent.evaluate(CapabilityRequest(
            platform="EVA",
            required_capabilities=["authentication", "biometric_liveness_check"],
        ))
        self.assertEqual(resp.status, SupportStatus.INSUFFICIENT_KNOWLEDGE.value)
        self.assertFalse(resp.supported)
        self.assertIn("biometric_liveness_check", resp.capabilities_needing_investigation)
        # It should NOT show up as supported or unsupported -- no invented answer.
        self.assertNotIn("biometric_liveness_check", resp.supported_capabilities)
        self.assertNotIn("biometric_liveness_check", resp.unsupported_capabilities)

    # 6. Conflicting knowledge documents -----------------------------------------

    def test_conflicting_knowledge(self):
        resp = self.agent.evaluate(CapabilityRequest(
            platform="LEGACY_PORTAL",
            required_capabilities=["document_upload", "authentication"],
        ))
        self.assertEqual(resp.status, SupportStatus.INSUFFICIENT_KNOWLEDGE.value)
        self.assertFalse(resp.supported)
        self.assertEqual(len(resp.conflicts), 1)
        conflict = resp.conflicts[0]
        self.assertEqual(conflict.capability, "document_upload")
        self.assertIn("legacy-portal-platform-capabilities-addendum.md", conflict.supported_in)
        self.assertIn("legacy-portal-platform-capabilities.md", conflict.unsupported_in)
        # authentication is unambiguous across both docs, should still resolve.
        self.assertIn("authentication", resp.supported_capabilities)
        # confidence should be reduced by the conflict, but not zero
        self.assertGreater(resp.confidence, 0.0)
        self.assertLess(resp.confidence, 1.0)

    # 7. Platform documented but not yet approved (governance-pending) --------
    # Distinct from "unknown platform": knowledge exists (new-portal-platform-
    # capabilities.md, status: draft) but hasn't cleared governance, so it must
    # not be retrievable — and the caller must be able to tell the two cases
    # apart from `status` alone, without parsing `reasoning` text.

    def test_platform_pending_approval(self):
        resp = self.agent.evaluate(CapabilityRequest(
            platform="NEW_PORTAL",
            required_capabilities=["form_input"],
        ))
        self.assertEqual(resp.status, SupportStatus.PLATFORM_PENDING_APPROVAL.value)
        self.assertNotEqual(resp.status, SupportStatus.UNKNOWN_PLATFORM.value)
        self.assertFalse(resp.supported)
        self.assertEqual(resp.confidence, 0.0)
        self.assertEqual(resp.capabilities_needing_investigation, ["form_input"])

    def test_pending_approval_tool_calls_return_not_retrievable(self):
        result = self.agent.get_platform_capabilities("NEW_PORTAL")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "not_retrievable")

        result = self.agent.check_supported_component("NEW_PORTAL", "form_input")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "not_retrievable")

    # -- hardening: malformed knowledge fails loudly -------------------------

    def test_malformed_capability_bullet_raises_instead_of_silently_dropping(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "bad.md").write_text(
                "---\n"
                "document_id: PLT-BAD-001\n"
                "platform: BADPLAT\n"
                "status: approved\n"
                "---\n\n"
                "## Supported Capabilities\n"
                "- authentication: missing the backticks around the capability id\n"
            )
            with self.assertRaises(ValueError):
                load_knowledge_base(d)

    # -- hardening: explicit `supersedes` outranks authority_rank ------------

    def test_conflict_hint_prefers_explicit_supersedes_over_authority_rank(self):
        # Deliberately construct a case where the numerically higher
        # authority_rank is on the SUPERSEDED (stale) document, so a hint
        # based on rank alone would point at the wrong file. The higher-
        # authority hint must follow the explicit `supersedes` declaration
        # instead.
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a-old.md").write_text(
                "---\n"
                "document_id: PLT-X-001\n"
                "platform: X\n"
                "status: approved\n"
                "authority_rank: 90\n"
                "---\n\n"
                "## Supported Capabilities\n"
                "- `document_upload`: old doc says yes\n"
            )
            Path(d, "b-new.md").write_text(
                "---\n"
                "document_id: PLT-X-002\n"
                "platform: X\n"
                "status: approved\n"
                "authority_rank: 10\n"
                "supersedes: [PLT-X-001]\n"
                "---\n\n"
                "## Unsupported Capabilities\n"
                "- `document_upload`: new doc says no, this replaces the old assessment\n"
            )
            agent = PlatformCapabilityAgent(knowledge_dir=d)
            resp = agent.evaluate(CapabilityRequest(
                platform="X", required_capabilities=["document_upload"],
            ))
            self.assertEqual(len(resp.conflicts), 1)
            self.assertEqual(resp.conflicts[0].higher_authority_source, "PLT-X-002")

    # -- extra coverage -----------------------------------------------------

    def test_capability_alias_normalization(self):
        resp = self.agent.evaluate(CapabilityRequest(
            platform="EVA",
            required_capabilities=["auth", "file upload"],
        ))
        self.assertIn("authentication", resp.supported_capabilities)
        self.assertIn("document_upload", resp.supported_capabilities)

    def test_platform_name_case_and_spacing_insensitive(self):
        resp = self.agent.evaluate(CapabilityRequest(
            platform="  eva  ",
            required_capabilities=["authentication"],
        ))
        self.assertEqual(resp.platform, "eva_dbu")
        self.assertTrue(resp.supported)

    def test_eva_dbu_alias_matches_eva_knowledge(self):
        resp = self.agent.evaluate(CapabilityRequest(
            platform="eva_dbu",
            required_capabilities=["authentication"],
        ))
        self.assertEqual(resp.platform, "eva_dbu")
        self.assertTrue(resp.supported)

    def test_empty_requirements_raises(self):
        with self.assertRaises(ValueError):
            self.agent.evaluate(CapabilityRequest(platform="EVA", required_capabilities=[]))

    def test_response_is_json_serializable(self):
        import json
        resp = self.agent.evaluate(CapabilityRequest(
            platform="LEGACY_PORTAL",
            required_capabilities=["document_upload"],
        ))
        json.dumps(resp.to_dict())  # should not raise

    def test_shared_knowledge_base_companions_load(self):
        """Production companions under Knowledge_Base/Level 3 must be loadable."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        shared = repo_root / "Knowledge_Base" / "Level 3 - Platform Knowledge"
        if not shared.is_dir():
            self.skipTest("shared Knowledge_Base not present")
        agent = PlatformCapabilityAgent(knowledge_dir=str(shared))
        self.assertIn("eva_dbu", agent.knowledge_index)
        self.assertIn("asknow", agent.knowledge_index)
        # Narrative docs must not be ingested as capability sources.
        for pk in agent.knowledge_index.values():
            for sf in pk.source_files:
                self.assertIn("capabilities", sf)
                self.assertNotEqual(sf, "PLATFORM_IDS.md")


if __name__ == "__main__":
    unittest.main()
