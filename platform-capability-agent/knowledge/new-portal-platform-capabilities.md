---
document_id: PLT-NEWPORTAL-001
level: 3
level_name: platform
domain: web_banking
product: null
platform: NEW_PORTAL
platform_full_name: Next-Gen Customer Portal (in development)
tags: [new-portal, web, draft]
status: draft
version: 0.3
last_updated: 2026-08-01
authority_rank: 80
supersedes: []
conflicts_with: []
---

# New Portal Platform Capabilities (DRAFT — not yet approved)

This document describes the planned capabilities of the Next-Gen Customer
Portal, currently under design. It has not gone through governance review
and must not be treated as retrievable platform knowledge until its status
changes to `approved`.

## Supported Capabilities

- `authentication`: Planned to support passkey and biometric authentication.
- `form_input`: Planned to support dynamic multi-step forms.
- `document_upload`: Planned to support drag-and-drop upload with virus scanning.
- `api_action`: Planned to support GraphQL-based backend actions.

## Unsupported Capabilities

- `native_camera_capture`: Not planned for the web portal.

## Constraints

- `document_upload`: Draft spec only — final component and file-size limits not yet confirmed.

## Notes

This file exists specifically to test that the agent's knowledge loader
correctly excludes non-approved documents from retrieval, per the
metadata contract's `status` field.
