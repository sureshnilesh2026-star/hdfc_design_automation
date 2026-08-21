# 02 — Alias

**Depends on**: 01-Primitives
**Referenced by**: 03-Semantics
**Scope**: one-time, shared across all brands (see `skills/brand-theming`).
Every token has a Light and Dark value.

---

## brand/logo
| Token | Light | Dark |
|---|---|---|
| primary | identity/hdfc-blue | identity/hdfc-blue |
| secondary | identity/hdfc-red | identity/hdfc-red |
| tertiary | basic/white | basic/white |

Constant across modes — brand identity shouldn't shift with theme.

## surface/root
| Token | Light | Dark |
|---|---|---|
| light | basic/white | grey/900 |
| dark | grey/900 | basic/white |
| opacity | basic/transparent | basic/transparent |

## surface/static (fixed, doesn't change per theme)
| Token | Light | Dark |
|---|---|---|
| white | basic/white | basic/white |
| neutral | grey/800 | grey/800 |
| warning | orange/500 | orange/500 |
| success | green/500 | green/500 |
| error | red/500 | red/500 |

---

## The 7-step ramp pattern
Applied identically across every color family below:
`lighter · light · base · dark · darker · on-light · on-dark`

## surface/primary (blue)
| Token | Light | Dark |
|---|---|---|
| lighter | blue/50 | blue/900 |
| light | blue/200 | blue/700 |
| base | blue/500 | blue/400 |
| dark | blue/700 | blue/200 |
| darker | blue/800 | blue/100 |
| on-light | blue/600 | blue/300 |
| on-dark | blue/100 | blue/800 |

## surface/primary/interactive
| Token | Light | Dark |
|---|---|---|
| foreground | blue/500 | blue/300 |
| hover-fill | blue/400 | blue/500 |
| disabled-fill | blue/200 *(open — proposed fix: grey/200)* | grey/700 |
| disabled-fg | blue/200 *(open — proposed fix: grey/400)* | grey/400 |
| disabled-fill 2 | blue/50 *(open — kept distinct, proposed fix: grey/100)* | grey/700 |
| disabled-fg 2 | blue/50 *(open — kept distinct, proposed fix: grey/300)* | grey/400 |

**Open item**: `disabled-fill`/`disabled-fg` resolve to the same Light-mode
value (contrast bug). `disabled-fg 2`/`disabled-fill 2` are intentionally
kept as a second, distinct pair (not deleted) but their exact intended
purpose and final values are still unconfirmed — see `09-open-items.md`.

## surface/neutral (grey)
| Token | Light | Dark |
|---|---|---|
| lighter | grey/50 | grey/800 |
| light | grey/200 | grey/700 |
| base | grey/500 | grey/300 |
| dark | grey/700 | grey/200 |
| darker | grey/900 | grey/50 |
| on-light | grey/600 | grey/300 |
| on-dark | slate/100 | grey/700 |

## surface/slate
| Token | Light | Dark |
|---|---|---|
| lighter | slate/50 | slate/900 |
| light | slate/200 | slate/700 |
| base | slate/500 | slate/300 |
| dark | slate/700 | slate/200 |
| darker | slate/900 | slate/50 |
| on-light | slate/600 | slate/300 |
| on-dark | slate/100 | slate/800 |

## surface/success (green)
| Token | Light | Dark |
|---|---|---|
| lighter | green/50 | green/900 |
| light | green/200 | green/700 |
| base | green/500 | green/400 |
| dark | green/700 | green/200 |
| darker | green/800 | green/100 |
| on-light | green/600 | green/300 |
| on-dark | green/100 | green/800 |

## surface/error (red)
| Token | Light | Dark |
|---|---|---|
| lighter | red/50 | red/900 |
| light | red/200 | red/700 |
| base | red/500 | red/400 |
| dark | red/700 | red/200 |
| darker | red/800 | red/100 |
| on-light | red/600 | red/300 |
| on-dark | red/100 | red/800 |

## surface/warning (orange)
| Token | Light | Dark |
|---|---|---|
| lighter | orange/50 | orange/900 |
| light | orange/200 | orange/700 |
| base | orange/500 | orange/400 |
| dark | orange/700 | orange/200 |
| darker | orange/800 | orange/100 |
| on-light | orange/600 | orange/300 |
| on-dark | orange/100 | orange/800 |

## surface/info (light-blue)
| Token | Light | Dark |
|---|---|---|
| lighter | light-blue/50 | light-blue/900 |
| light | light-blue/200 | light-blue/700 |
| base | light-blue/500 | light-blue/400 |
| dark | light-blue/700 | light-blue/200 |
| darker | light-blue/800 | light-blue/100 |
| on-light | light-blue/600 | light-blue/300 |
| on-dark | light-blue/100 | light-blue/800 |

## surface/accent/purple
| Token | Light | Dark |
|---|---|---|
| lighter | purple/50 | purple/900 |
| light | purple/200 | purple/700 |
| base | purple/500 | purple/400 |
| dark | purple/700 | purple/200 |
| darker | purple/800 | purple/100 |
| on-light | purple/600 | purple/300 |
| on-dark | purple/100 | purple/800 |

## surface/accent/rust (brown)
| Token | Light | Dark |
|---|---|---|
| lighter | brown/50 | brown/900 |
| light | brown/200 | brown/700 |
| base | brown/500 | brown/400 |
| dark | brown/700 | brown/200 |
| darker | brown/800 | brown/100 |
| on-light | brown/600 | brown/300 |
| on-dark | brown/100 | brown/800 |

## surface/accent/yellow
| Token | Light | Dark |
|---|---|---|
| lighter | yellow/50 | yellow/900 |
| light | yellow/200 | yellow/700 |
| base | yellow/500 | yellow/400 |
| dark | yellow/700 | yellow/200 |
| darker | yellow/800 | yellow/100 |
| on-light | yellow/600 | yellow/300 |
| on-dark | yellow/100 | yellow/800 |

## surface/accent/violet
| Token | Light | Dark |
|---|---|---|
| lighter | violet/50 | violet/900 |
| light | violet/200 | violet/700 |
| base | violet/500 | violet/400 |
| dark | violet/700 | violet/200 |
| darker | violet/800 | violet/100 |
| on-light | violet/600 | violet/300 |
| on-dark | violet/100 | violet/800 |

---

## surface/elevation
| Token | Light | Dark |
|---|---|---|
| default | basic/white | grey/900 |

### subtle
| Property | Light | Dark |
|---|---|---|
| x / y / blur / spread | 0 / 1 / 2 / 0 | 0 / 1 / 2 / 0 |
| shadow-color | alpha/dark/200 | alpha/dark/600 |
| background-subtle | basic/white | grey/800 |

### moderate
| Property | Light | Dark |
|---|---|---|
| x / y / blur / spread | 0 / 4 / 8 / 0 | 0 / 4 / 8 / 0 |
| shadow-color | alpha/dark/100 | alpha/dark/600 |
| background-moderate | basic/white | grey/700 |

### intense
| Property | Light | Dark |
|---|---|---|
| x / y / blur / spread | 0 / 12 / 16 / 0 | 0 / 8 / 12 / 0 |
| shadow-color | alpha/dark/100 | alpha/dark/600 |
| background-intense | basic/white | grey/600 |

---

## gradients
### hero
| Stop | Light | Dark |
|---|---|---|
| 0 | 090C34 *(raw hex — open item)* | 0A0F1C *(raw hex — open item)* |
| 100 | 0F3167 *(raw hex — open item)* | 10183A *(raw hex — open item)* |

### bottom-nav
| Stop | Light | Dark |
|---|---|---|
| 0% & 100% | EAEBF0 *(raw hex)* | 252B3D *(raw hex)* |
| 20% & 80% | F49BB3 *(raw hex)* | 6C1831 *(raw hex)* |
| 50% | 3B5CE1 *(raw hex, same both modes)* | 3B5CE1 |

### icon
| Stop | Light | Dark |
|---|---|---|
| 0 | FFFFFF at 0% *(raw hex)* | FFFFFF at 0% |
| 100 | 010003 *(raw hex)* | 010003 |

**Open item**: all gradient stops use raw hex instead of referencing
`global-colors/*` primitives — breaks rebrand-safety for these three
gradients specifically. See `09-open-items.md`.
