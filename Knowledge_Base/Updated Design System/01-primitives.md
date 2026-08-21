# 01 — Primitives

**Depends on**: nothing (foundation layer)
**Referenced by**: 02-Alias, 04-Layout, 05-Typography, 06-Adaptive

## Rule for this layer
Raw, context-free values only. Never named after usage — `blue/500`, not
`action.primary`. This is the only layer where raw numbers/hex are
acceptable (with the two documented exceptions below).

---

## Color ramps — `global-colors/*`

### basic
| Token | Hex |
|---|---|
| black | 000000 |
| white | FFFFFF |
| transparent | FFFFFF (0% alpha) |

### identity (brand swatches, not a ramp)
| Token | Hex |
|---|---|
| hdfc-blue | 014790 |
| hdfc-red | FF2D16 |

### blue
| Step | Hex |
|---|---|
| 50 | F3F6FD |
| 100 | E1E9FE |
| 200 | 9CB4F7 |
| 300 | 6D8FF8 |
| 400 | 3B5CE1 |
| 500 | 1C3FCA |
| 600 | 1F30AD |
| 700 | 112266 |
| 800 | 162150 |
| 900 | 11162D |

### grey
| Step | Hex |
|---|---|
| 50 | F5F5F5 |
| 100 | ECECEC |
| 200 | D9D9D9 |
| 300 | B3B3B3 |
| 400 | 757575 |
| 500 | 444444 |
| 600 | 383838 |
| 700 | 2C2C2C |
| 800 | 1E1E1E |
| 900 | 111111 |

### slate
| Step | Hex |
|---|---|
| 50 | F9FAFF |
| 100 | EDEDF1 |
| 200 | BBBCC3 |
| 300 | 9EA0AA |
| 400 | 7E838F |
| 500 | 5C6172 |
| 600 | 3E4457 |
| 700 | 252B3D |
| 800 | 1B2137 |
| 900 | 10182D |

### green
| Step | Hex |
|---|---|
| 50 | EFFAF2 |
| 100 | DCF4ED |
| 200 | ACE5C9 |
| 300 | 76E2C0 |
| 400 | 50C898 |
| 500 | 00815A |
| 600 | 076246 |
| 700 | 0E4636 |
| 800 | 11362A |
| 900 | 10231D |

### orange
| Step | Hex |
|---|---|
| 50 | FEFAEC |
| 100 | FFF2D6 |
| 200 | F7C599 |
| 300 | F6A258 |
| 400 | DE7313 |
| 500 | B65805 |
| 600 | 804006 |
| 700 | 542D0B |
| 800 | 38210B |
| 900 | 2E1D10 |

### red
| Step | Hex |
|---|---|
| 50 | FDF1F4 |
| 100 | FFDDE6 |
| 200 | F49BB3 |
| 300 | EF7092 |
| 400 | E44771 |
| 500 | D61C53 |
| 600 | A30F3B |
| 700 | 6C1831 |
| 800 | 3C1620 |
| 900 | 261218 |

### vivid-red
| Step | Hex |
|---|---|
| 50 | FCE6E7 |
| 100 | F9C8CB |
| 200 | F28C92 |
| 300 | EC5861 |
| 400 | E93842 |
| 500 | E30613 |
| 600 | CF0511 |
| 700 | A1040D |
| 800 | 7D030A |
| 900 | 5F0308 |

### light-blue
| Step | Hex |
|---|---|
| 50 | EBFCFE |
| 100 | DBF9FE |
| 200 | B7EFFE |
| 300 | 79D7FB |
| 400 | 37BAF6 |
| 500 | 2A78C6 |
| 600 | 2974C1 |
| 700 | 2467AD |
| 800 | 153A65 |
| 900 | 142B4D |

### violet
| Step | Hex |
|---|---|
| 50 | F4F0FF |
| 100 | E2D8FF |
| 200 | C7B9FF |
| 300 | AD9AFC |
| 400 | 9077F4 |
| 500 | 7454F2 |
| 600 | 5236C9 |
| 700 | 3A268D |
| 800 | 241950 |
| 900 | 1D1537 |

### brown
| Step | Hex |
|---|---|
| 50 | FDEFED |
| 100 | F4DBD7 |
| 200 | E7BCB6 |
| 300 | DA9D95 |
| 400 | C37B6E |
| 500 | A85C51 |
| 600 | 85463C |
| 700 | 62342D |
| 800 | 3D221E |
| 900 | 261512 |

### yellow
| Step | Hex |
|---|---|
| 50 | FDFAE7 |
| 100 | FFF6E0 |
| 200 | FFE8AC |
| 300 | FFD86E |
| 400 | FEC93B |
| 500 | F2B102 |
| 600 | B38600 |
| 700 | 946F00 |
| 800 | 533F04 |
| 900 | 332E1B |

### purple
| Step | Hex |
|---|---|
| 50 | FDEDFA |
| 100 | F1D5F6 |
| 200 | E6B5EE |
| 300 | D894E4 |
| 400 | C36DD2 |
| 500 | A84AB8 |
| 600 | 893399 |
| 700 | 581F63 |
| 800 | 36163C |
| 900 | 241028 |

**Note**: `red` (calmer) and `vivid-red` (more urgent) are both defined
deliberately, for Semantics to draw on if a more alarming state beyond
standard "error" is ever needed.

---

## Numeric scale — `global-scale/*`
Single non-linear scale, token → px:

| Token | px | Token | px | Token | px | Token | px |
|---|---|---|---|---|---|---|---|
| 0 | 0 | 250 | 20 | 700 | 56 | 3000 | 240 |
| 25 | 2 | 300 | 24 | 750 | 60 | 3500 | 280 |
| 50 | 4 | 350 | 28 | 800 | 64 | 4000 | 320 |
| 75 | 6 | 400 | 32 | 900 | 72 | 4500 | 360 |
| 100 | 8 | 450 | 36 | 1000 | 80 | 5000 | 400 |
| 125 | 10 | 500 | 40 | 1100 | 88 | 6000 | 480 |
| 150 | 12 | 550 | 44 | 1200 | 96 | 7000 | 560 |
| 175 | 14 | 600 | 48 | 1500 | 120 | 8000 | 640 |
| 200 | 16 | 650 | 52 | 1750 | 140 | 9000 | 720 |
| 225 | 18 | | | 2000 | 160 | 9600 | 768 |
| | | | | 2500 | 200 | 12800 | 1024 |
| | | | | | | 16000 | 1280 |
| | | | | | | 18000 | 1440 |

Dense increments at the low end, sparse at the high end — this one scale is
reused by spacing, sizing, and radius, keeping them mathematically related.

---

## Alpha — `alpha/dark`, `alpha/light`
| Token | Base hex | Opacity |
|---|---|---|
| dark/100 | 000000 | 8% |
| dark/200 | 000000 | 12% |
| dark/300 | 111111 | 16% |
| dark/400 | 111111 | 40% |
| dark/500 | 111111 | 48% |
| dark/600 | 111111 | 64% |
| light/100 | FFFFFF | 4% |
| light/200 | FFFFFF | 8% |
| light/300 | FFFFFF | 12% |
| light/400 | FFFFFF | 48% |

---

## Primitive-type (font primitives)

### font/family
| Token | Value |
|---|---|
| inter | Inter |
| poppins | poppins |

### font/weight
| Token | Value |
|---|---|
| regular-400 | Regular |
| medium-500 | Medium |
| semibold-600 | Semi bold |
| bold-700 | Bold |
| italic-400 | Italic |

**Open item**: `italic-400` mixes a font-*style* into the font-*weight*
group — see `09-open-items.md`. Left as-is by decision.

### font/letter-spacing
| Token | Value |
|---|---|
| regular-400 | 0 |
| italic-400 | 0 |
| medium-500 | 0 |
| semibold-600 | -1% |
| bold-700 | -2% |

### font/size/display
| Token | Scale ref | px |
|---|---|---|
| lg | global-scale/600 | 48 |
| md | global-scale/550 | 44 |
| sm | global-scale/500 | 40 |

### font/size/heading
| Token | Scale ref | px |
|---|---|---|
| h1 | global-scale/450 | 36 |
| h2 | global-scale/400 | 32 |
| h3 | global-scale/350 | 28 |
| h4 | global-scale/300 | 24 |
| h5 | global-scale/250 | 20 |

### font/size/paragraph
| Token | Scale ref | px |
|---|---|---|
| lg | global-scale/225 | 18 |
| md | global-scale/200 | 16 |
| sm | global-scale/175 | 14 |
| xsm | global-scale/150 | 12 |

### font/paragraph-spacing
| Token | Scale ref | px |
|---|---|---|
| lg | global-scale/200 | 16 |
| md | global-scale/200 | 16 |
| sm | global-scale/150 | 12 |
| xsm | global-scale/100 | 8 |

**Open item**: `lg` and `md` are identical — see `09-open-items.md`. Left
as-is by decision.

### font/line-height/display
| Token | Scale ref | px |
|---|---|---|
| lg | global-scale/700 | 56 |
| md | global-scale/650 | 52 |
| sm | global-scale/600 | 48 |

### font/line-height/heading
| Token | Scale ref | px |
|---|---|---|
| h1 | global-scale/550 | 44 |
| h2 | global-scale/500 | 40 |
| h3 | global-scale/450 | 36 |
| h4 | global-scale/400 | 32 |
| h5 | global-scale/350 | 28 |

### font/line-height/paragraph
| Token | Scale ref | px |
|---|---|---|
| lg | global-scale/300 | 24 |
| md | global-scale/250 | 20 |
| sm | global-scale/225 | 18 |
| xsm | global-scale/200 | 16 |

---

## Layout primitives

### radius
| Token | Scale ref | px |
|---|---|---|
| 3xs | global-scale/0 | 0 |
| 2xs | global-scale/50 | 4 |
| xs | global-scale/75 | 6 |
| sm | global-scale/100 | 8 |
| md | global-scale/150 | 12 |
| lg | global-scale/200 | 16 |
| xl | global-scale/250 | 20 |
| 2xl | global-scale/300 | 24 |
| full | global-scale/18000 | 1440 (pill/circle) |

### spacing
| Token | Scale ref | px |
|---|---|---|
| 2xs | global-scale/25 | 2 |
| xs | global-scale/50 | 4 |
| sm | global-scale/100 | 8 |
| md | global-scale/150 | 12 |
| lg | global-scale/200 | 16 |
| xl | global-scale/250 | 20 |
| 2xl | global-scale/300 | 24 |
| 3xl | global-scale/350 | 28 |
| 4xl | global-scale/400 | 32 |
| 5xl | global-scale/500 | 40 |
| 6xl | global-scale/600 | 48 |
| 7xl | global-scale/800 | 64 |
| 8xl | global-scale/1000 | 80 |

### border (raw literals — intentional, see note below)
| Token | px |
|---|---|
| 2xs | 0.5 |
| xs | 1 |
| sm | 1.5 |
| md | 2 |
| lg | 2.5 |
| xl | 3 |

**Not a defect**: raw literals because `global-scale`'s minimum step (4px)
can't express hairline sub-pixel widths.

### size
| Token | Scale ref | px |
|---|---|---|
| xxs | global-scale/0 | 0 |
| xs | global-scale/100 | 8 |
| sm | global-scale/150 | 12 |
| md | global-scale/200 | 16 |
| lg | global-scale/250 | 20 |
| xl | global-scale/300 | 24 |
| 2xl | global-scale/350 | 28 |
| 3xl | global-scale/400 | 32 |
| 4xl | global-scale/450 | 36 |
| 5xl | global-scale/500 | 40 |
| 6xl | global-scale/600 | 48 |
| 7xl | global-scale/800 | 64 |
| 8xl | global-scale/1000 | 80 |
| 9xl | global-scale/1200 | 96 |
| 10xl | global-scale/1500 | 120 |
| 11xl | global-scale/1750 | 140 |
| 12xl | global-scale/2000 | 160 |
| 13xl | global-scale/2500 | 200 |
| 14xl | global-scale/3000 | 240 |
| 15xl | global-scale/3500 | 280 |
| 16xl | global-scale/4000 | 320 |

### margin (per breakpoint)
| Breakpoint | Scale ref | px |
|---|---|---|
| mobile | global-scale/200 | 16 |
| tablet | global-scale/400 | 32 |
| desktop | global-scale/700 | 56 |
| large-desktop | *(open — proposed global-scale/900 / 72px, not yet applied)* | — |

### gutter (per breakpoint)
| Breakpoint | Scale ref | px |
|---|---|---|
| mobile | global-scale/100 | 8 |
| tablet | global-scale/200 | 16 |
| desktop | global-scale/250 | 20 |
| large-desktop | *(open — proposed global-scale/300 / 24px, not yet applied)* | — |

### screen-behaviour (raw literals — intentional breakpoints)
| Breakpoint | px |
|---|---|
| mobile | 360 |
| tablet | 768 |
| desktop | 1280 |
| large-desktop | 1440 |

## Documentation coverage
Full page-doc sets exist for: Color, Spacing, Typography, Global-scale,
Accessibility, Border, Gradients, Elevation, and Grids — usage guidelines,
token structure, WCAG 2.2 compliance reference.
