---
document_id: PLT-LEGACYPORTAL-001
level: 3
level_name: platform
domain: web_banking
product: null
platform: LEGACY_PORTAL
platform_full_name: Legacy Customer Self-Service Portal
tags: [legacy-portal, web, browser-based, historical]
status: approved
version: 1.4
last_updated: 2024-08-01
authority_rank: 40
supersedes: []
conflicts_with: [PLT-LEGACYPORTAL-002]
---

# Legacy Portal Platform Capabilities (Addendum — Original Onboarding Doc)

Older reference document from the original portal build. Kept for historical
traceability. NOTE: this document has not been reconciled with the 2026 assessment
in `legacy-portal-platform-capabilities.md` and may be stale.

## Supported Capabilities

- `document_upload`: Supports file upload via the ActiveX upload control for scanned
  KYC documents.
- `authentication`: Supports username/password login.

## Unsupported Capabilities

- `native_camera_capture`: No camera integration available.

## Constraints

- `document_upload`: Requires the ActiveX browser plugin to be installed; only
  supported on Internet Explorer.

## Notes

This document predates the 2025 browser-compatibility update that removed ActiveX
support. It is retained for historical reference only.
