# Selection Button — Component Spec

Extracted from Figma — **"Final Selection button"**
([node 5360:32399](https://www.figma.com/design/Afu8S0vVgbGLRWTcZCiHYG/Foundations_for-AI?node-id=5360-32399)).
Consolidated 2026-08-19. Sibling component to `selection-card.md`. See also
`08-components.md` and `09-open-items.md`.

A compact, tappable **selection button** — used to pick an entity (e.g. a
bank account) inside a flow. Shows an account label, an optional masked
account number, an optional balance amount, a decorative illustration, and
a check badge in the selected state.

Two axes (2 × 2 = **4 states**):

| Axis | Values |
|---|---|
| **Size** | `medium` · `small` |
| **State** | `default` · `selected` |

Single brand in this frame — **EVA_DBU** (uses the `evadbu/changeaddress`
illustration). No per-brand (HDFC / EVA_MB) variants were present in this
node. Source symbols: medium default `5360:33003`, medium selected
`5360:33208`, small default `5360:33113`, small selected `5360:33283`.

---

## 1. Sizes

| Size | Dimensions (w×h) | Padding | Radius | Gap | Content shown |
|---|---|---|---|---|---|
| **medium** | 296×104 | `selection-button/.../medium/padding-x` (20px) | `selection-button/.../medium/radius` (32px) | `selection-button/.../medium/gap` (24px) | label + masked number + balance amount + illustration (120px) + check badge (selected) |
| **small** | 144×72 | 16px (raw) | 20px (raw) | 24px | 2-line label + illustration (80px) + check badge (selected) — **no** number, **no** amount |

- **medium** is the "rich" variant: a top row of `label` (left) + masked
  account number (right), then a large balance `amount` beneath.
- **small** is the "compact" variant: just a two-line label
  ("Saving / Account"); the number and amount are dropped.
- **Illustration** is anchored top-right and clipped by the button's
  `overflow:hidden` — 120px on medium, 80px on small.

> Small size uses **raw literals** (`padding 16px`, `radius 20px`) rather
> than named `selection-button/.../small/*` tokens like medium does — an
> inconsistency worth repointing. Logged in `09-open-items.md`.

---

## 2. States (per size)

### Background & border

| Property | default | selected |
|---|---|---|
| background-color | `selection-button/default/background-color/default` → `#c0cdff` (light periwinkle) | `selection-button/selected/background-color/default` → deep-blue gradient (`#3f61f2 → #274ce0 → #1b3ac6`, ≈`#0024b0` token base brightened by the sheen) |
| border (frame) | `border/border-color-white` → white, 1px | **none** — the selected frame has no stroke (`selection-button/selected/border-color/default` → transparent `rgba(255,255,255,0)`) |
| foreground (text) | label `#111` (static), number `#5c6172` (disabled) | all text white |
| shadow | `0 12px 24px rgba(116,129,178,0.4)` | same |

### Highlight overlay (both states)

A `mix-blend-mode: plus-lighter` radial-gradient sheen sits above the fill:

| State | Gradient stop color | Opacity |
|---|---|---|
| default | cream `rgba(245,240,221,1)` → transparent | 0.24 |
| selected | white `rgba(255,255,255,1)` → transparent | 0.71 |

The selected state's brighter, whiter sheen reinforces the darker fill.

### Success ticker / check badge (selected only)

Source: Figma `Success` component ([node 5456:43432](https://www.figma.com/design/Afu8S0vVgbGLRWTcZCiHYG/Foundations_for-AI?node-id=5456-43432)).
Both sizes use the **same 32×32 ticker**:

| Property | Value |
|---|---|
| size | **32 × 32 px** (both medium & small) |
| circle fill | **white** |
| circle border | **1.5px `#1C3FCA`** (both sizes) |
| check color | `#1C3FCA` |
| check stroke | **medium selected → 1.5px** · **small selected → 2px** (rounded caps/joins) |

**Position** (within the card):

| Size | Position |
|---|---|
| medium | top-right corner — `right ≈ 12px / top ≈ 11px` (badge center ≈ `left 252 / top 11`) |
| small | `left ≈ 100px / top ≈ 5px` (overlaps the top of the pin illustration) |

Default state shows **no** ticker.

> Because both sizes share the 32px ticker, it reads proportionally larger
> on the smaller (144px-wide) button — matching the Figma frame.

---

## 3. Content elements

| Element | Sample | Sizes | Typography role |
|---|---|---|---|
| Label | "Saving Account" (medium, 1 line) / "Saving\nAccount" (small, 2 lines) | both | `static/paragraph/extrasmall/medium-500` — Inter Medium 12px / lh 16 |
| Masked number | "\*\*\*\*\*7673" | medium only | `responsive/paragraph/p4/medium-500` — Inter Medium 12px / lh 16, right-aligned |
| Balance amount | "₹5,00,000" | medium only | `static/heading/h3/semibold-600` — Inter SemiBold 28px / lh 36 / ls −1 |
| Illustration | `illustration/evadbu/changeaddress` | both (120px / 80px) | — |
| Check badge | success tick | selected only | — |

Dev-facing props observed on the Figma component: `displayText`
(amount), `showDisplayText`, `text`/`text1`/`text3` (label), `text2`
(number), `showText2`, `property1` (size+state combined).

---

## 4. Resolved values — quick reference

| | medium default | medium selected | small default | small selected |
|---|---|---|---|---|
| size | 296×104 | 296×104 | 144×72 | 144×72 |
| padding | 20px | 20px | 16px | 16px |
| radius | 32px | 32px | 20px | 20px |
| background | `#c0cdff` | blue gradient | `#c0cdff` | blue gradient |
| frame border | white, 1px | **none** | white, 1px | **none** |
| text color | `#111` / `#5c6172` | white | `#111` | white |
| illustration | 120px | 120px | 80px | 80px |
| ticker | — | 32px, border 1.5px, **check 1.5px** | — | 32px, border 1.5px, **check 2px** |
| balance amount | ✓ | ✓ | — | — |
| masked number | ✓ | ✓ | — | — |

Interactive demo: `selection-button.html` (switch Size × State; click a
button to toggle default ⇄ selected).

---

## 5. Status & open items

Status: ⚠️ **Extracted 2026-08-19, pending formal validation.**

Open items (to add to `09-open-items.md` → "Selection Button"):
1. **small** size uses raw literals (`padding 16`, `radius 20`) instead of
   named `selection-button/.../small/*` tokens (medium is tokenized).
2. **selected** border is a bound token that resolves to fully-transparent
   white (`rgba(255,255,255,0)`) — harmless (alpha 0) but, like the
   Selection Card / Button secondary cases, an unbound-looking value worth
   a cleaner token.
3. Only the **EVA_DBU** brand is present in this frame — no HDFC / EVA_MB
   equivalents located yet; flag if they exist and need documenting.
