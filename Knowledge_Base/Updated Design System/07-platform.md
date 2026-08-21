# 07 — Platform (full token values)

Depends on: 06-Adaptive. Referenced by: 08-Components (conditionally).
Lightweight, PWA-appropriate scope: conditional visibility flags, not deep
native-device conventions (tap targets, safe-areas, OS radius) — those are
deferred until true native apps exist.

## platform (columns: web, app)
| Token | web | app |
|---|---|---|
| platform | "web" | "app" |
| only web | True | False |
| only app | False | True |

## Usage
A component checks `only web` / `only app` as a boolean condition to decide
whether it renders in a given context (e.g. hide a "Add to Home Screen"
prompt when `only app = true`). Open question (unconfirmed): whether
`platform` is also meant to drive value swaps downstream, the way `brand`
does at Semantics — flag if this pattern emerges in Components.
