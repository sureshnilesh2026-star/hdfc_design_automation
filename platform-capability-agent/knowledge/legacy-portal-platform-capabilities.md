---
document_id: PLT-LEGACYPORTAL-002
level: 3
level_name: platform
domain: web_banking
product: null
platform: LEGACY_PORTAL
platform_full_name: Legacy Customer Self-Service Portal
tags: [legacy-portal, web, browser-based]
status: approved
version: 2.0
last_updated: 2026-01-10
authority_rank: 80
supersedes: [PLT-LEGACYPORTAL-001]
conflicts_with: [PLT-LEGACYPORTAL-001]
---

# Legacy Portal Platform Capabilities

The Legacy Portal is the older browser-based self-service portal, scheduled for
gradual replacement by NetBanking 2.0. This document reflects the current (2026)
platform team assessment.

## Supported Capabilities

- `authentication`: Supports username/password login with OTP as a second factor.
- `form_input`: Supports standard HTML forms.
- `api_action`: Supports server-side API calls via the portal backend.

## Unsupported Capabilities

- `document_upload`: The ActiveX-based upload component was deprecated and removed in
  the 2025 browser-compatibility update. No replacement has been implemented yet.
- `native_camera_capture`: Browser-based portal has no camera integration.
- `offline_mode`: Requires an active session; no offline support.

## Constraints

- `authentication`: Sessions expire after 20 minutes of inactivity.
- `form_input`: Forms do not support inline validation; validation occurs on submit
  only.

## Notes

This document supersedes any earlier capability notes for the Legacy Portal.
Document upload has been unsupported since the 2025 update — see the addendum for
historical context.
