---
document_id: PLT-IVR-001
level: 3
level_name: platform
domain: voice_banking
product: null
platform: IVR
platform_full_name: Interactive Voice Response System
tags: [ivr, voice, phone-banking]
status: approved
version: 1.0
last_updated: 2026-04-15
authority_rank: 80
supersedes: []
conflicts_with: []
---

# IVR Platform Capabilities

IVR is HDFC's phone-based automated voice system. It has no visual UI, so journeys are
limited to voice prompts, DTMF (keypad) input, and voice recognition.

## Supported Capabilities

- `authentication`: Supports OTP delivered via voice call and DTMF-entered PIN
  verification.
- `voice_input`: Supports spoken input parsed via speech recognition.
- `dtmf_input`: Supports keypad entry for numeric input (account numbers, amounts,
  menu selection).
- `api_action`: Supports backend API calls triggered after a completed voice step.
- `otp_verification`: Supports OTP request and verification via voice/DTMF.

## Unsupported Capabilities

- `form_input`: IVR has no visual interface and cannot render structured forms.
- `document_upload`: IVR has no mechanism to receive files.
- `native_camera_capture`: IVR has no visual or camera interface.
- `geolocation_capture`: IVR cannot access caller device location.
- `status_tracking`: IVR does not support persistent visual status updates; only
  end-of-call voice confirmation is available.

## Constraints

- `voice_input`: Voice recognition accuracy depends on call quality and background
  noise; a DTMF fallback must be offered for any voice_input step.
- `api_action`: Calls must complete within the active call session; there is no
  asynchronous callback mechanism within a single call.
- `authentication`: Maximum 3 failed PIN attempts before the call is routed to an
  agent.

## Notes

IVR is suitable only for simple, linear, low-data journeys (balance enquiry, PIN
reset via OTP, block/unblock card). Any journey requiring visual forms, document
upload, or camera capture cannot be implemented on IVR.
