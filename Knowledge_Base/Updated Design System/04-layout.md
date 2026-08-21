# 04 — Layout (full token values)

Depends on: 03-Semantics (for naming rationale), 01-Primitives (spacing/
radius/margin/gutter), 06-Adaptive (for the responsive repoint — see below).
Usage-intent tokens for spacing, radius, and containers. Confirmed complete.

## Spacing roles
| Token | Points to (adaptive-aware) | Mobile px | Rationale |
|---|---|---|---|
| layout.spacing.card-padding | responsive/spacing/xl | 20 | Card internal padding |
| layout.spacing.section-gap | responsive/spacing/2xl | 24 | Gap between major page sections |
| layout.spacing.form-field-gap | responsive/spacing/lg | 16 | Gap between stacked form fields |
| layout.spacing.list-item-gap | responsive/spacing/md | 12 | Gap between list rows |

*(Originally pointed at flat `spacing/*` primitives; repointed to
`responsive/spacing/*` once 06-Adaptive existed — see 09-open-items.md
history. This repoint is confirmed correct/needed but final Figma
application should be verified.)*

## Radius roles
| Token | Points to (adaptive-aware) | Mobile px | Rationale |
|---|---|---|---|
| layout.radius.card | responsive/radius/lg | 16→ (see adaptive table) | Soft, modern surface rounding |
| layout.radius.button | responsive/radius/md | 12→ | Tighter than card, high-frequency element |
| layout.radius.input | responsive/radius/sm | 8→ | Structural/precise, form context |
| layout.radius.modal | responsive/radius/2xl | 24→ | Most prominent surface, biggest radius |

Hierarchy: input < button < card < modal — softer corners track higher
surface prominence. `radius/full` is reserved for circular/pill elements
(avatar, badge, toggle, radio) and referenced directly, no Layout role
needed.

## Container roles
| Token | Mobile | Tablet | Desktop | Large-desktop |
|---|---|---|---|---|
| layout.container.padding-inline | margin/horizontal = 16 | 32 | 56 | 56 (open item: primitive gap, see 09-open-items.md) |
| layout.container.max-width | — | — | screen-behaviour/desktop = 1280 | screen-behaviour/large-desktop = 1440 |

Container roles are inherently responsive by nature — their breakpoint
behavior is formalized at 06-Adaptive, not re-declared here.
