# Platform IDs (canonical contract)

Shared vocabulary for Intent Recognition and Platform Capability agents.
Machine-readable capability slices are the `*-capabilities.md` companions in this
directory — not the narrative Level 3 prose docs.

## Canonical IDs

| Canonical ID | Intent enum | Companion file | Narrative doc |
|---|---|---|---|
| `eva_dbu` | `Platform.EVA_DBU` | `3.1-eva-capabilities.md` (`PLT-EVA-CAP-001`) | `3.1 - EVA DBU.md` (`PLT-EVA-001`) |
| `asknow` | `Platform.ASKNOW` | `3.2-asknow-capabilities.md` (`PLT-ASK-CAP-001`) | `3.2 - AskNow.md` (`PLT-ASK-001`) |
| `web` | `Platform.WEB` | _(none yet)_ | — |
| `mobile_native` | `Platform.MOBILE_NATIVE` | _(none yet)_ | — |

## Aliases (capability agent `normalize_platform`)

| Input | Resolves to |
|---|---|
| `eva`, `EVA`, `eva_dbu`, `dbu` | `eva_dbu` |
| `asknow`, `ASKNOW`, `ask_now` | `asknow` |

Other labels are lowercased snake_case as-is (e.g. `IVR` → `ivr`).

## Channel → platform (intent gate)

| `channel_hint` | Platform |
|---|---|
| `eva`, `eva_dbu`, `dbu` | `eva_dbu` |
| `asknow` | `asknow` |
| `web`, `netbanking` | `web` |
| `mobile`, `mobile_native`, `mobilebanking` | `mobile_native` |
