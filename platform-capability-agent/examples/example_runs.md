# Example Runs

These are real outputs from running `cli.py` against the sample knowledge base in
`knowledge/`, one per required test scenario. Reproduce any of them with:

```bash
python3 cli.py --platform <PLATFORM> --requirements "<comma,separated,list>"
```

---

## 1. Platform supports everything requested

```bash
python3 cli.py --platform EVA --requirements "authentication,form_input,document_upload,api_action"
```

```json
{
  "platform": "EVA",
  "status": "fully_supported",
  "supported": true,
  "requested_capabilities": ["authentication", "form_input", "document_upload", "api_action"],
  "supported_capabilities": ["authentication", "form_input", "document_upload", "api_action"],
  "unsupported_capabilities": [],
  "capabilities_needing_investigation": [],
  "conflicts": [],
  "knowledge_sources": ["eva-platform-capabilities.md"],
  "confidence": 1.0
}
```

---

## 2. Platform supports only some requirements (the brief's own example)

```bash
python3 cli.py --platform EVA --requirements "authentication,form input,document upload,api call,camera capture"
```

```json
{
  "platform": "EVA",
  "status": "partially_supported",
  "supported": false,
  "supported_capabilities": ["authentication", "form_input", "document_upload", "api_action"],
  "unsupported_capabilities": ["native_camera_capture"],
  "capabilities_needing_investigation": [],
  "conflicts": [],
  "constraints": [
    "Document upload must use the platform's supported attachment component. Direct file-system or camera-based capture is not available as an upload source."
  ],
  "knowledge_sources": ["eva-platform-capabilities.md"],
  "confidence": 1.0
}
```

Note free-text input ("form input", "camera capture") normalizes to the same
canonical IDs as snake_case input — see `agent/normalize.py`.

---

## 3. Platform supports none of the requirements

```bash
python3 cli.py --platform IVR --requirements "form_input,document_upload,native_camera_capture"
```

```json
{
  "platform": "IVR",
  "status": "not_supported",
  "supported": false,
  "supported_capabilities": [],
  "unsupported_capabilities": ["form_input", "document_upload", "native_camera_capture"],
  "capabilities_needing_investigation": [],
  "conflicts": [],
  "knowledge_sources": ["ivr-platform-capabilities.md"],
  "confidence": 1.0
}
```

Confidence is **1.0**, not low — the agent has unambiguous documentation that
none of these are supported. Confidence measures certainty of the answer, not
how favorable the answer is.

---

## 4. Platform is unknown

```bash
python3 cli.py --platform WHATSAPP_BOT --requirements "authentication,form_input"
```

```json
{
  "platform": "WHATSAPP_BOT",
  "status": "unknown_platform",
  "supported": false,
  "supported_capabilities": [],
  "unsupported_capabilities": [],
  "capabilities_needing_investigation": ["authentication", "form_input"],
  "conflicts": [],
  "knowledge_sources": [],
  "confidence": 0.0,
  "reasoning": [
    "No approved knowledge document found for platform 'WHATSAPP_BOT'.",
    "Known (approved) platforms: EVA, IVR, LEGACY_PORTAL.",
    "Refusing to guess capabilities for an undocumented or unapproved platform."
  ]
}
```

---

## 4b. Platform is documented but not yet approved (distinct from unknown)

`WHATSAPP_BOT` above has **no** knowledge file at all. `NEW_PORTAL` does — but
it's `status: draft` (`knowledge/new-portal-platform-capabilities.md`), so it
must not be retrievable, and the caller must be able to tell these two
situations apart from `status` alone.

```bash
python3 cli.py --platform NEW_PORTAL --requirements "form_input,document_upload"
```

```json
{
  "platform": "NEW_PORTAL",
  "status": "platform_pending_approval",
  "supported": false,
  "supported_capabilities": [],
  "unsupported_capabilities": [],
  "capabilities_needing_investigation": ["form_input", "document_upload"],
  "conflicts": [],
  "knowledge_sources": [],
  "confidence": 0.0,
  "reasoning": [
    "No approved knowledge document found for platform 'NEW_PORTAL'.",
    "Note: documentation exists for 'NEW_PORTAL' but is not yet approved for retrieval: PLT-NEWPORTAL-001 (status=draft). This is different from no documentation existing at all — flag for governance follow-up rather than treating it as fully unknown.",
    "Known (approved) platforms: EVA, IVR, LEGACY_PORTAL.",
    "Refusing to guess capabilities for an undocumented or unapproved platform."
  ]
}
```

The two read-only tools (`get_platform_capabilities`, `check_supported_component`)
agree: calling either for `NEW_PORTAL` returns `{"ok": false, "error": {"code": "not_retrievable", ...}}`
rather than silently exposing the draft data.

---

## 5. Knowledge base does not contain enough information

```bash
python3 cli.py --platform EVA --requirements "authentication,biometric_liveness_check"
```

```json
{
  "platform": "EVA",
  "status": "insufficient_knowledge",
  "supported": false,
  "supported_capabilities": ["authentication"],
  "unsupported_capabilities": [],
  "capabilities_needing_investigation": ["biometric_liveness_check"],
  "conflicts": [],
  "knowledge_sources": ["eva-platform-capabilities.md"],
  "confidence": 0.35,
  "reasoning": [
    "...",
    "'biometric_liveness_check': not documented for EVA in any known source. Not assuming support or non-support.",
    "Overall status: insufficient_knowledge (confidence 0.35)."
  ]
}
```

`biometric_liveness_check` is not asserted as either supported or unsupported —
it is surfaced separately so a human (or the journey planner) knows exactly
what still needs investigation.

---

## 6. Two knowledge documents contain conflicting information

```bash
python3 cli.py --platform LEGACY_PORTAL --requirements "document_upload,authentication"
```

```json
{
  "platform": "LEGACY_PORTAL",
  "status": "insufficient_knowledge",
  "supported": false,
  "supported_capabilities": ["authentication"],
  "unsupported_capabilities": [],
  "capabilities_needing_investigation": [],
  "conflicts": [
    {
      "capability": "document_upload",
      "supported_in": ["legacy-portal-platform-capabilities-addendum.md"],
      "unsupported_in": ["legacy-portal-platform-capabilities.md"],
      "higher_authority_source": "PLT-LEGACYPORTAL-002"
    }
  ],
  "knowledge_sources": [
    "legacy-portal-platform-capabilities-addendum.md",
    "legacy-portal-platform-capabilities.md"
  ],
  "confidence": 0.25
}
```

`knowledge/legacy-portal-platform-capabilities-addendum.md` is a 2024 doc that
says document upload is supported via an ActiveX plugin;
`knowledge/legacy-portal-platform-capabilities.md` is the current 2026 doc
saying it was removed. The agent does not silently prefer one — it surfaces
the conflict with both sources named, and drops overall confidence sharply.

`higher_authority_source` is informational only, never used to auto-resolve
the conflict. Here it points at `PLT-LEGACYPORTAL-002` (the 2026 doc) because
that doc's frontmatter explicitly declares `supersedes: [PLT-LEGACYPORTAL-001]`
— an explicit governance declaration is checked before falling back to the
numeric `authority_rank` field, since the two are supposed to agree but
nothing enforces that at authoring time.
