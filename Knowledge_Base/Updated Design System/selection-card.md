# Selection Card — Component Spec

Extracted from Figma — **"Final DBU selection card"**
([node 5294:31993](https://www.figma.com/design/Afu8S0vVgbGLRWTcZCiHYG/Foundations_for-AI?node-id=5294-31993)).
Consolidated 2026-08-19. Companion interactive demo: `selection-card.html`
(switch Brand × Size × Mode freely). See also `08-components.md` →
"Selection Card" and `09-open-items.md`.

A selectable content card — leading icon or chip, title, optional
description, optional illustration, optional location line, plus a checkbox
affordance — used for choice-style selection (e.g. picking a branch / DBU
option).

Three axes, fully independent (3 × 4 × 2 = **24 states**):

| Axis | Values |
|---|---|
| **Brand** | `dbu` (EVA_DBU) · `nb/mb` (EVA_MB) · `hdfc` (HDFC) |
| **Size** | `small` · `medium` · `large` · `xlarge` |
| **Mode** | `default` · `selected` |

Source frames: generic `card size` reference (`5287:19018`) + one
Default/Selected pair per brand — EVA_DBU (`5287:24657`), EVA_MB /
"nb/mb" (`5287:25481`), HDFC (`5287:25556`).

---

## 1. Sizes (content is size-driven)

| Size | Dimensions (w×h) | Gap | Content shown |
|---|---|---|---|
| **small**  | 296×80  | `global-scale/100` (8px)          | leading icon + title only + checkbox (vertically centered, right edge) |
| **medium** | 296×100 | `selectioncard/size/medium/gap` (4px) | leading icon + title + 1-line description + checkbox (top-right) |
| **large**  | 296×132 | `global-scale/300` (24px)         | chip ("Chips") + title + description + illustration (120px, bottom-right) + checkbox (top-right) — no leading icon |
| **xlarge** | 296×156 | `global-scale/300` (24px)         | everything in `large` + a location row (16px pin icon + "100M Away") |

- **Leading icon** (small/medium): 32px glyph inside a 64px circle,
  background `hdfc/primary/50` (`#f3f6fd`), radius `corner-radius/80`.
- **Illustration** (large/xlarge): the EVA_DBU `updateemail` illustration,
  120px, anchored bottom-right, clipped by the card's `overflow:hidden`.
- **Width is fixed at 296px and height is fixed per size** — toggling
  Mode never changes the footprint (see §4).

> **Naming issue** — the padding-x token is literally named
> `selectioncard/size/xlarge/padding-x` on **all four** size variants
> (small/medium/large reference the `xlarge` token name, not their own).
> Resolved values differ, but the token *names* don't disambiguate. Logged
> in `09-open-items.md`.

### Padding per size × brand

| Size | dbu | nb/mb | hdfc |
|---|---|---|---|
| small  | 16px | 16px | 16px |
| **medium** | **20px** | **16px** | **16px** |
| large  | 16px | 16px | 16px |
| xlarge | 16px | 16px | 16px |

*(medium is the only size with a per-brand padding split — dbu = 20px, the
other two = 16px.)*

---

## 2. Brands (style is brand-driven)

Radius is **not** size-driven here (unlike Button / Input Field) — it is
brand-driven, and scales up dbu → nb/mb → hdfc-inverse:

| Property | dbu (EVA_DBU) | nb/mb (EVA_MB) | hdfc (HDFC) |
|---|---|---|---|
| **Radius** | 24px (most rounded) | 20px | 16px (least rounded) |

### Default mode — resolved values (xlarge)

| Property | dbu | nb/mb | hdfc |
|---|---|---|---|
| background-color | `rgba(255,255,255,0.24)` | `rgba(255,255,255,0.3)` | `white` (opaque) |
| border-color | white | white | white |
| border-width | 1 (generic, unnamed) | 1 (generic, unnamed) | 1 (generic, unnamed) |

### Selected mode — resolved values (xlarge)

| Property | dbu | nb/mb | hdfc |
|---|---|---|---|
| background-color | gradient (violet→blue→violet): `rgba(161,98,248,0.16)` → `rgba(83,105,218,0.16)` → `rgba(161,98,248,0.16)` | `#e1e9fe` (solid) | `#f3f6fd` (solid) |
| border-color | `#1c3fca` | `#1c3fca` | `#1c3fca` |
| border-width | **2** (`selectioncard/size/border-width`) | 1 (unchanged) | 1 (unchanged) |
| chip on select | **restyled** → fill `chips/filled/background-color/neutral` (`rgba(255,255,255,0.56)`), text `#3a268d` | unchanged (blue fill, white text) | unchanged (blue fill, white text) |

> **Only dbu** changes border-width and chip color on selection; nb/mb and
> hdfc only swap background/border color. Reads as dbu deliberately making
> its selected state more prominent — not a 1:1 token reskin across brands.

> **Token-naming inconsistency** — hdfc's selected border is bound to a
> token named
> `selectioncard/selected/background-color/selected/foreground-color/default`
> (a "foreground-color" token setting a *border*). nb/mb and dbu use a
> sensibly-named `.../border-color/default` for the same `#1c3fca` value.
> Not visually broken; logged in `09-open-items.md`.

---

## 3. Checkbox (nested `control/checkbox`)

| Property | Default | Selected |
|---|---|---|
| background | transparent | `control/background-color/default` (`#1c3fca`), all brands |
| border-color | dbu: `#e1e9fe` (pale) · nb/mb & hdfc: `#1c3fca` (brand blue) | n/a (filled) |
| radius | dbu: 8px · nb/mb & hdfc: 4px | same |
| tick icon | present but hidden (`opacity:0`) | visible, white |

> dbu's unselected checkbox border (`#e1e9fe`) is noticeably lower-contrast
> than nb/mb & hdfc's brand-blue border for the same state — flagged as a
> possible contrast gap in `09-open-items.md`.

---

## 4. Selected state must NOT resize the card

Requirement: switching `default` ⇄ `selected` keeps the exact same
footprint, even though dbu's selected border goes 1px → 2px.

Achieved with:
- **fixed `width:296px` + fixed `height` per size** (80 / 100 / 132 / 156), and
- **`box-sizing:border-box`** — so the extra 1px of border on dbu-selected
  grows *inward* rather than expanding the outer box.

Verified computed values (medium size):

| Brand / mode | padding | border | height |
|---|---|---|---|
| dbu / default | 20px | 1px | 100px |
| dbu / selected | 20px | 2px | 100px |
| nb/mb / default | 16px | 1px | 100px |
| nb/mb / selected | 16px | 1px | 100px |
| hdfc / default | 16px | 1px | 100px |
| hdfc / selected | 16px | 1px | 100px |

---

## 5. Status & open items

Status: ⚠️ **Extracted 2026-08-19, pending formal validation.**

Open items (see `09-open-items.md` → "Selection Card"):
1. Padding-x token named `.../xlarge/padding-x` on all four sizes.
2. hdfc selected border bound to a `foreground-color`-named token.
3. dbu unselected checkbox border low-contrast (`#e1e9fe`).
4. Default `border-width` is a generic unnamed `1` (only dbu-selected uses
   the named `selectioncard/size/border-width` = 2).
