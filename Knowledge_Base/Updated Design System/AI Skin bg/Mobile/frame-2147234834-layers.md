# Frame 2147234834 — Layer Documentation

Source: [Figma](https://www.figma.com/design/Afu8S0vVgbGLRWTcZCiHYG/Foundations_for-AI?node-id=5330-24068)

## Background (actual export)

Real PNG export from Figma — exact visual match, not a CSS approximation.

![Frame 2147234834 background](frame-2147234834-bg.png)

## Overview

| Property | Value |
|---|---|
| Name | Frame 2147234834 |
| Node ID | `5330:24068` |
| Type | FRAME |
| Position | x: 32, y: 2098 |
| Dimensions | 360 × 752 |
| Visible | Yes |
| Opacity | 1 |
| Fills | None |
| Strokes | None |
| Effects | None |
| Clips Content | No |
| Blend Mode | PASS_THROUGH |

## Layer Tree

```
FRAME "Frame 2147234834" [5330:24068] 360x752
  └── INSTANCE "Theme" [5330:24059] 360x752
        └── FRAME "BG" [I5330:24059;5299:4372] 1358x1810
              ├── RECTANGLE "64e9502e4159bed6f8f57b071db5ac7e 2" [I5330:24059;5299:4373] 1810x1358
              ├── FRAME "Gradient circles" [I5330:24059;5299:4374] 360x752
              │     ├── ELLIPSE "Ellipse 6469" [I5330:24059;5299:4375] 411x411
              │     ├── ELLIPSE "Ellipse 6473" [I5330:24059;5299:4376] 411x411
              │     ├── ELLIPSE "Ellipse 6472" [I5330:24059;5299:4377] 411x411
              │     └── ELLIPSE "Ellipse 6470" [I5330:24059;5299:4378] 367x367
              └── RECTANGLE "Rectangle 48118123" [I5330:24059;5299:4379] 360x423
```

Structure verified against Figma `get_metadata` — matches exactly.

## Layer Details

### 1. Theme (Instance)

| Property | Value |
|---|---|
| Node ID | `5330:24059` |
| Type | INSTANCE |
| Component | `theme=nb/mb mobile` |
| Position | x: 0, y: 752 |
| Dimensions | 360 × 752 |
| Opacity | 1 |
| Fills | Solid `#ffffff` |
| Clips Content | Yes |
| Blend Mode | PASS_THROUGH |

### 2. BG (Frame)

| Property | Value |
|---|---|
| Node ID | `I5330:24059;5299:4372` |
| Type | FRAME |
| Position | x: -535, y: -501 |
| Dimensions | 1358 × 1810 |
| Opacity | 1 |
| Fills | None |
| Clips Content | Yes |
| Blend Mode | PASS_THROUGH |

### 3. 64e9502e4159bed6f8f57b071db5ac7e 2 (Rectangle)

| Property | Value |
|---|---|
| Node ID | `I5330:24059;5299:4373` |
| Type | RECTANGLE |
| Position | x: 0, y: 0 |
| Dimensions | 1810 × 1358 |
| Opacity | 0.5 |
| Fills | Image fill (FILL) + solid `#203ca7` |
| Effects | Layer Blur, radius 100 |
| Blend Mode | MULTIPLY |

### 4. Gradient circles (Frame)

| Property | Value |
|---|---|
| Node ID | `I5330:24059;5299:4374` |
| Type | FRAME |
| Position | x: 535, y: 501 |
| Dimensions | 360 × 752 |
| Opacity | 0.2 |
| Fills | None |
| Clips Content | No |
| Blend Mode | PASS_THROUGH |

### 5. Ellipse 6469

| Property | Value |
|---|---|
| Node ID | `I5330:24059;5299:4375` |
| Type | ELLIPSE |
| Position | x: 166, y: 772 |
| Dimensions | 411 × 411 |
| Opacity | 1 |
| Fills | Linear gradient `#79b8fe` → `#ddd9ff` |
| Effects | Layer Blur, radius 300 |
| Blend Mode | PASS_THROUGH |

### 6. Ellipse 6473

| Property | Value |
|---|---|
| Node ID | `I5330:24059;5299:4376` |
| Type | ELLIPSE |
| Position | x: -260, y: 922 |
| Dimensions | 411 × 411 |
| Opacity | 1 |
| Fills | Linear gradient `#79b8fe` → `#ddd9ff` |
| Effects | Layer Blur, radius 300 |
| Blend Mode | PASS_THROUGH |

### 7. Ellipse 6472

| Property | Value |
|---|---|
| Node ID | `I5330:24059;5299:4377` |
| Type | ELLIPSE |
| Position | x: -168, y: 331 |
| Dimensions | 411 × 411 |
| Opacity | 1 |
| Fills | Solid `#34c6ef` |
| Effects | Layer Blur, radius 300 |
| Blend Mode | PASS_THROUGH |

### 8. Ellipse 6470

| Property | Value |
|---|---|
| Node ID | `I5330:24059;5299:4378` |
| Type | ELLIPSE |
| Position | x: -158, y: 297 |
| Dimensions | 367 × 367 |
| Opacity | 1 |
| Fills | Linear gradient `#ddd9ff` → `#ffffff` |
| Effects | Layer Blur, radius 100 |
| Blend Mode | PASS_THROUGH |

### 9. Rectangle 48118123

| Property | Value |
|---|---|
| Node ID | `I5330:24059;5299:4379` |
| Type | RECTANGLE |
| Position | x: 535, y: 423 |
| Dimensions | 360 × 423 |
| Opacity | 1 |
| Fills | Linear gradient `#f0f4fd` → `#f0f4fd` |
| Effects | None |
| Blend Mode | PASS_THROUGH |

## Color Palette

| Color | Hex | RGB | Used In |
|---|---|---|---|
| White | `#ffffff` | 255, 255, 255 | Theme fill, Ellipse 6470 gradient end |
| Deep Blue | `#203ca7` | 32, 60, 167 | Background rectangle solid fill |
| Sky Blue | `#79b8fe` | 121, 184, 254 | Ellipse 6469 & 6473 gradient start |
| Lavender | `#ddd9ff` | 221, 217, 255 | Ellipse 6469/6473 gradient end, 6470 start |
| Cyan | `#34c6ef` | 52, 198, 239 | Ellipse 6472 solid fill |
| Ice Blue | `#f0f4fd` | 240, 244, 253 | Rectangle 48118123 gradient |

## Visual Effects Summary

| Layer | Effect | Radius |
|---|---|---|
| Background rectangle | Layer Blur | 100 |
| Ellipse 6469 | Layer Blur | 300 |
| Ellipse 6473 | Layer Blur | 300 |
| Ellipse 6472 | Layer Blur | 300 |
| Ellipse 6470 | Layer Blur | 100 |

## Animation / Motion

Checked via Figma's motion/keyframe API on both the frame (`5330:24068`) and the Theme instance (`5330:24059`), recursive — **no native keyframe or Smart Animate motion data returned** (empty result both times).

What this means:
- No animated properties (position, opacity, rotation) are attached to these layers through Figma's Animation panel / motion tooling.
- The "quick animation" you're seeing is most likely a **prototype transition** (e.g. a Smart Animate swap between `theme` variants, or an interactive/auto-animate flow triggered elsewhere in the file) — that class of data isn't exposed by the read tools available here.
- To pin down the exact animation (trigger, duration, easing), check the **Prototype tab** in Figma directly on this frame and the `Theme` component's variants, since it's not retrievable via the API from this session.

## Notes

- The frame's only child is a **Theme** component instance (`theme=nb/mb mobile`) — the entire background composition lives inside it.
- Background effect = blurred image/solid rectangle at 50% opacity (Multiply) + soft gradient ellipses at 20% container opacity.
- Gradient circles are heavily blurred (radius 300) ellipses in blue/cyan/lavender — ambient glow effect.
- Bottom rectangle (ice-blue gradient) fades the lower portion of the frame.
- `frame-2147234834-bg.png` (in this same folder) is the real Figma-exported PNG, used above for exact visual match — not a CSS recreation.
