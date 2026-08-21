# Frame 2147234833 (DBU BG) — Layer Documentation

Source: [Figma](https://www.figma.com/design/Afu8S0vVgbGLRWTcZCiHYG/Foundations_for-AI?node-id=5330-24058)

## Background (actual export)

Real PNG export from Figma — exact visual match, not a CSS approximation.

![DBU BG](dbu%20bg%20%28figma%20export%29.png)

## Overview

| Property | Value |
|---|---|
| Name | Frame 2147234833 |
| Node ID | `5330:24058` |
| Type | FRAME |
| Position | x: 2078, y: 2098 |
| Dimensions | 360 × 800 |

## Layer Tree

```
FRAME "Frame 2147234833" [5330:24058] 360x800
  └── INSTANCE "Theme" [5330:23980] 360x800
        ├── ROUNDED-RECTANGLE "White Gradient" [I5330:23980;5299:5852] 360x180  (hidden)
        ├── FRAME "BG" [I5330:23980;5299:5853] 443x985
        │     ├── ROUNDED-RECTANGLE "image 28" [I5330:23980;5299:5854] 480x880  (hidden)
        │     ├── ROUNDED-RECTANGLE "Moving bg animation" [I5330:23980;5299:5855] 1395x1860  (hidden)
        │     ├── FRAME "BG" [I5330:23980;5299:5856] 2059x1574
        │     │     ├── ROUNDED-RECTANGLE "image 2715" [I5330:23980;5299:5857] 1603x1230
        │     │     ├── ROUNDED-RECTANGLE "64e9502e4159bed6f8f57b071db5ac7e 1" [I5330:23980;5299:5858] 2059x1544
        │     │     ├── ROUNDED-RECTANGLE "dd50b6932dfd6ff35c020c63f7e1213f 1" [I5330:23980;5299:5859] 1208x906  (hidden)
        │     │     ├── ELLIPSE "Ellipse 6391" [I5330:23980;5299:5860] 820x820
        │     │     ├── ELLIPSE "Ellipse 6393" [I5330:23980;5299:5861] 734x734
        │     │     └── ELLIPSE "Ellipse 6392" [I5330:23980;5299:5862] 820x820
        │     ├── ELLIPSE "Ellipse 11117" [I5330:23980;5299:5863] 279x279
        │     └── INSTANCE "Pattern" [I5330:23980;5299:5864] 1311x1294
        ├── FRAME "Bottom Navigation" [I5330:23980;5299:5865] 360x68  (hidden)
        └── INSTANCE "Home Indicator" [I5330:23980;5299:5909] 360x24
```

Structure pulled directly from Figma `get_metadata` on the `Theme` instance (`5330:23980`).

## Notable Layers

| Layer | Node ID | Note |
|---|---|---|
| White Gradient | `I5330:23980;5299:5852` | Hidden — top fade, not currently active |
| **Moving bg animation** | `I5330:23980;5299:5855` | Hidden layer, literally named for the background motion — see Animation section below |
| image 28 | `I5330:23980;5299:5854` | Hidden — alternate/base image variant |
| dd50b6932dfd6ff35c020c63f7e1213f 1 | `I5330:23980;5299:5859` | Hidden — alternate blend/mask shape |
| Pattern | `I5330:23980;5299:5864` | Instance — the wavy line texture overlaying the gradient |
| Ellipse 6391 / 6392 / 6393 | — | The 3 large blurred gradient orbs forming the blue/purple wash |
| Home Indicator | `I5330:23980;5299:5909` | iOS home-bar component, visible |
| Bottom Navigation | `I5330:23980;5299:5865` | Hidden — not part of this composition |

## Animation / Motion

This frame has a layer explicitly named **"Moving bg animation"** (`I5330:23980;5299:5855`, a 1395×1860 rounded-rectangle) — strong signal that the background is meant to move.

Checked Figma's motion/keyframe API directly on this node and recursively on the whole `Theme` instance — **no native keyframe data returned** in either case.

What this means:
- The layer is currently marked **hidden**, alongside two other hidden alternates (`White Gradient`, `image 28`, `dd50b6932dfd6ff35c020c63f7e1213f 1`) — this pattern (multiple hidden sibling states) usually means the motion is driven by a **Smart Animate prototype interaction** that swaps between these layer states, not a native keyframe/Animation-panel effect.
- That class of animation isn't exposed by the read tools available here.
- To see the actual motion (trigger, duration, easing), open the **Prototype tab** on this frame in Figma and step through the interaction that toggles `Moving bg animation` visible.

## Notes

- `dbu bg (figma export).png` (same folder) is the real Figma-exported PNG used above — exact visual match, not a CSS recreation.
- The visible composition = 3 large blurred ellipses (blue/purple gradient orbs) + a wavy-line `Pattern` instance overlay + a white fade at the bottom.
- Several sibling layers are hidden alternates (background image variants, gradient masks) not part of the currently rendered state.
