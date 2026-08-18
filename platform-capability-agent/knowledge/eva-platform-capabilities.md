---
document_id: PLT-EVA-001
level: 3
level_name: platform
domain: conversational_banking
product: null
platform: eva_dbu
platform_full_name: Enterprise Virtual Assistant
tags: [eva, eva_dbu, journey-orchestration, conversational-ui]
status: approved
version: 1.2
last_updated: 2026-06-01
authority_rank: 80
supersedes: []
conflicts_with: []
---

# EVA Platform Capabilities

EVA is HDFC's conversational assistant platform, embedded in mobile banking and web
banking. Journeys on EVA are built from a fixed set of conversational UI components
plus backend action hooks. EVA does not have access to native device hardware APIs.

## Supported Capabilities

- `authentication`: Supports OTP-based authentication and MPIN re-verification via the
  platform's built-in auth component. Biometric authentication is delegated to the host
  app (mobile banking) when EVA is embedded there.
- `form_input`: Supports structured multi-field forms with client-side validation,
  rendered as conversational form cards.
- `document_upload`: Supports file attachment through the platform's attachment
  component (PDF, JPG, PNG up to 5MB).
- `api_action`: Supports synchronous and asynchronous backend API calls through the
  platform's action framework, with retry and timeout handling.
- `otp_verification`: Supports OTP request and verification as a first-class step type.
- `status_tracking`: Supports polling and webhook-based status updates surfaced back to
  the user as conversational messages.

## Unsupported Capabilities

- `native_camera_capture`: EVA cannot invoke the device camera directly. There is no
  camera API exposed to the conversational layer.
- `geolocation_capture`: EVA cannot read device GPS location.
- `push_notification_trigger`: EVA cannot originate push notifications; notifications
  must be triggered by the host app or a separate notification service.
- `offline_mode`: EVA requires an active network connection; there is no offline queuing
  of conversational steps.

## Constraints

- `document_upload`: Document upload must use the platform's supported attachment
  component. Direct file-system or camera-based capture is not available as an upload
  source.
- `authentication`: Session expires after 10 minutes of inactivity; long-running
  journeys must be able to resume after re-authentication.
- `api_action`: Backend API calls must complete within 15 seconds or must be modeled as
  asynchronous with a status-tracking step.
- `form_input`: Forms are limited to 12 fields per card; longer forms must be split
  across multiple conversational steps.

## Notes

EVA is best suited for structured, linear journeys (verification, updates, simple
applications). Journeys requiring native hardware access (camera, GPS) or offline
support should be routed to the mobile banking app instead of EVA.
