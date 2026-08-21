# 03 — Semantics

**Depends on**: 02-Alias
**Referenced by**: 04-Layout, 05-Typography, 08-Components
**Naming pattern**: `category.role.property` (3 segments)
**Brand columns**: HDFC · EVA_MB · EVA_DBU — all three currently resolve to
**identical** Alias references (intentional interim state; see
`skills/brand-theming`). Values below are shown once since all three
brands match today — if a value ever diverges by brand, it will be shown
per-column.

---

## page
| Token | Value |
|---|---|
| subtle | surface/root/light |
| moderate | surface/neutral/lighter |

## text
| Token | Value |
|---|---|
| subtle | surface/neutral/base |
| default | surface/neutral/darker |
| strong | surface/neutral/dark |
| inverse | surface/root/light |
| disabled | surface/neutral/light |
| static | surface/static/white |

## text/primary
| Token | Value |
|---|---|
| default | surface/primary/interactive/foreground |
| secondary | surface/primary/on-light |
| disabled | surface/primary/light |
| hover | surface/primary/interactive/hover-fill |

## text/success
| Token | Value |
|---|---|
| default | surface/success/on-light |
| inverse | surface/success/on-dark |

## text/warning
| Token | Value |
|---|---|
| default | surface/warning/base |

## text/danger
| Token | Value |
|---|---|
| default | surface/error/base |

## text/info
| Token | Value |
|---|---|
| default | surface/info/base |

## text/family
| Token | Value |
|---|---|
| family | font/family/inter *(open item: should be font/family/inter for HDFC, font/family/poppins for EVA_MB & EVA_DBU — fix defined, not yet applied — see 09-open-items.md)* |

---

## cards/neutral
| Token | Value |
|---|---|
| subtle | surface/root/light |
| moderate | surface/neutral/lighter |
| strong | surface/neutral/light |

## cards/primary
| Token | Value |
|---|---|
| subtle | surface/primary/lighter |
| moderate | surface/primary/light |

---

## feedback/background-color
| Group | subtle | moderate | intense |
|---|---|---|---|
| primary | surface/primary/lighter | surface/primary/base | — |
| neutral | surface/neutral/lighter | surface/neutral/light | surface/static/neutral |
| info | surface/info/lighter | surface/info/base | — |
| success | surface/success/lighter | surface/static/success | — |
| warning | surface/warning/lighter | surface/static/warning | — |
| error | surface/error/lighter | surface/static/error | — |
| violet | surface/accent/violet/lighter | surface/accent/violet/base | — |
| purple | surface/accent/purple/lighter | surface/accent/purple/base | — |
| rust | surface/accent/rust/lighter | surface/accent/rust/base | — |
| yellow | surface/accent/yellow/lighter | surface/accent/yellow/base | — |

## feedback/border-color
| Group | subtle | moderate | intense |
|---|---|---|---|
| primary | surface/primary/light | — | — |
| neutral | surface/neutral/lighter | surface/neutral/light | surface/neutral/base |
| info | surface/info/light | — | — |
| success | surface/success/light | — | — |
| warning | surface/warning/light | — | — |
| error | surface/error/light | — | — |
| violet | surface/accent/violet/light | — | — |
| purple | surface/accent/purple/light | — | — |
| rust | surface/accent/rust/light | — | — |
| yellow | surface/accent/yellow/light | — | — |

## feedback/icon-color (all "subtle" tier)
| Group | Value |
|---|---|
| primary | surface/primary/interactive/foreground |
| neutral | surface/neutral/dark |
| info | surface/info/base |
| success | surface/success/base |
| warning | surface/warning/base |
| error | surface/error/base |
| violet | surface/accent/violet/base |
| purple | surface/accent/purple/base |
| rust | surface/accent/rust/base |
| yellow | surface/accent/yellow/darker |
| static | surface/static/white |

## feedback/text-color (all "subtle" tier unless noted)
| Group | Value |
|---|---|
| primary | surface/primary/interactive/foreground |
| neutral | surface/neutral/dark |
| info | surface/info/base |
| success | surface/success/base |
| warning | surface/warning/base |
| error | surface/error/base |
| violet | surface/accent/violet/on-light |
| purple | surface/accent/purple/base |
| rust | surface/accent/rust/base |
| yellow | surface/accent/yellow/darker |
| static (subtle) | surface/static/white |
| static (intense) | surface/static/neutral |

---

## icon
| Token | Value |
|---|---|
| subtle | surface/neutral/base |
| default | surface/neutral/darker |
| strong | surface/neutral/dark |
| inverse | surface/root/light |
| disabled | surface/neutral/light |
| static | surface/static/white |

## icon/primary
| Token | Value |
|---|---|
| subtle | surface/primary/light |
| default | surface/primary/base |
| strong | surface/primary/dark |

## icon/success
| Token | Value |
|---|---|
| subtle | surface/success/light |
| default | surface/success/base |
| strong | surface/success/darker |

## icon/warning
| Token | Value |
|---|---|
| subtle | surface/warning/light |
| default | surface/warning/base |
| strong | surface/warning/darker |

## icon/danger
| Token | Value |
|---|---|
| subtle | surface/error/light |
| default | surface/error/base |
| strong | surface/error/darker |

## icon/info
| Token | Value |
|---|---|
| subtle | surface/info/light |
| default | surface/info/base |
| strong | surface/info/darker |

## icon/purple, /rust, /yellow, /violet
Same subtle/default/strong pattern, each referencing its own
`surface/accent/{family}/light`, `/base`, `/darker` (yellow uses `/darker`
naming variant consistent with the family above).

---

## border
| Token | Value |
|---|---|
| default | surface/neutral/light |
| inverse | surface/root/light |
| static | surface/static/white |
| strong | surface/neutral/base |
| disabled | surface/primary/light |

## border/primary
| Token | Value |
|---|---|
| subtle | surface/primary/interactive/foreground |
| default | surface/primary/interactive/hover-fill |
| brand | surface/primary/base |
| strong | surface/primary/on-light |
| disabled | surface/primary/interactive/disabled-fg |

---

## visual/icon (sizes)
| Token | Value |
|---|---|
| xs | size/xs |
| sm | size/sm |
| md | size/md |
| lg | size/lg |
| xl | size/xl |
| 2xl | size/3xl |
| 3xl | size/5xl |

## visual/icon-stroke (sizes)
| Token | Value |
|---|---|
| 2xs | border/2xs |
| xs | border/xs |
| sm | border/sm |
| md | border/md |
| lg | border/lg |

## visual/illustration (sizes)
| Token | Value |
|---|---|
| xs | size/6xl |
| sm | size/7xl |
| md | size/8xl |
| lg | size/9xl |
| xl | size/10xl |
| 2xl | size/11xl |
| 3xl | size/12xl |
| 4xl | size/13xl |
| 5xl | size/14xl |
| 6xl | size/15xl |
| 7xl | size/16xl |

**Applied catalog**: the EVA_DBU illustration set (19 items,
`illustration/evadbu/*`) is documented in `assets-illustrations.md`, shown
at `md` (80px) and `xl` (120px) — both exact token matches. A third
requested size, 60px, has **no exact token** in this scale (nearest are
`xs`/48px, `sm`/64px) — see `09-open-items.md` → "Assets — Illustrations".

## visual/logo (sizes)
| Token | Value |
|---|---|
| xs | size/xs |
| sm | size/sm |
| md | size/md |
| lg | size/lg |
| xl | size/xl |
| 2xl | size/3xl |
| 3xl | size/5xl |
| 4xl | size/6xl |

---

## Component-named groups (NOT true Semantics — see `skills/tokens-semantics`)
`control`, `input-field`, `button`, `chips`, `separator`, `bottomsheet`,
`popover`, `tabs`, `pagination`, `avatar`, `badge` — these are pre-built
**08-Components-layer** work sitting in the same Figma collection for
convenience. Full detail lives in `08-components.md`, not here.

**Button, per-brand (confirmed 2026-08-19)**: `button/*` tokens carry
real, verified brand divergence — HDFC and EVA_DBU share the same brand-blue
Primary background and 12px radius; EVA_MB uses a near-white Primary
background, dark-neutral text, and a 24px pill radius instead. Full
resolved values, all 4 button types × 4 states × 3 brands, in
`08-components.md` → "Button". A prior version of that doc claimed
EVA_MB/EVA_DBU Primary resolved to error/success colors — re-verified
directly against Figma and that was wrong; corrected.

## Known open items
See `09-open-items.md` → "03-Semantics" section.
