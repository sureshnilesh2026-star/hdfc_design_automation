# 06 — Adaptive (full token values)

Depends on: 03-Semantics, 04-Layout, 05-Typography (as the source values
being selected between). Referenced by: 07-Platform, 08-Components.
4 breakpoints: **mobile / tablet / desktop / large-desktop**.

## responsive/font/size
Diagonal cascade — every role shifts up exactly one step per breakpoint.
| Token | mobile | tablet | desktop | large-desktop |
|---|---|---|---|---|
| h1 | heading/h1 | display/sm | display/md | display/lg |
| h2 | heading/h2 | heading/h1 | display/sm | display/md |
| h3 | heading/h3 | heading/h2 | heading/h1 | display/sm |
| h4 | heading/h4 | heading/h3 | heading/h2 | heading/h1 |
| h5 | heading/h5 | heading/h4 | heading/h3 | heading/h2 |
| p1 | paragraph/lg | heading/h5 | heading/h4 | heading/h3 |
| p2 | paragraph/md | paragraph/lg | heading/h5 | heading/h4 |
| p3 | paragraph/sm | paragraph/md | paragraph/lg | heading/h5 |
| p4 | paragraph/xsm | paragraph/sm | paragraph/md | paragraph/lg |

## responsive/font/lineheight
Same cascade pattern, mirrored per row above (h1: heading/h1 → display/sm →
display/md → display/lg; p1–p4 follow the equivalent paragraph/heading
line-height chain). Full detail in Figma; structurally identical to the
size table above, one field type over.

## responsive/radius
| Token | mobile | tablet | desktop | large-desktop |
|---|---|---|---|---|
| 2xs | radius/2xs | radius/2xs | radius/sm | radius/sm |
| xs | radius/sm | radius/sm | radius/sm | radius/md |
| sm | radius/md | radius/md | radius/lg | radius/lg |
| md | radius/lg | radius/lg | radius/xl | radius/2xl |
| lg | radius/xl | radius/xl | radius/2xl | radius/2xl |
| xl | radius/2xl | radius/2xl | radius/2xl | radius/2xl |
| full | radius/full | radius/full | radius/full | radius/full |
| bottomsheet | radius/3xs | radius/xl | radius/2xl | radius/2xl |

## responsive/spacing
| Token | mobile | tablet | desktop | large-desktop |
|---|---|---|---|---|
| 2xs | spacing/2xs | spacing/2xs | spacing/xs | spacing/xs |
| xs | spacing/xs | spacing/xs | spacing/sm | spacing/sm |
| sm | spacing/sm | spacing/sm | spacing/md | spacing/md |
| md | spacing/md | spacing/md | spacing/lg | spacing/xl |
| lg | spacing/lg | spacing/lg | spacing/xl | spacing/2xl |
| xl | spacing/xl | spacing/2xl | spacing/3xl | spacing/4xl |
| 2xl | spacing/2xl | spacing/3xl | spacing/4xl | spacing/5xl |
| 3xl | spacing/3xl | spacing/4xl | spacing/5xl | spacing/6xl |
| 4xl | spacing/4xl | spacing/5xl | spacing/6xl | spacing/7xl |
| 5xl | spacing/5xl | spacing/6xl | spacing/7xl | spacing/8xl |
| negative overlap | -32 | -32 | -32 | -60 |
| bottomsheet-top | spacing/sm | spacing/2xl | spacing/4xl | spacing/4xl |

## responsive/font/margin
| Token | mobile | tablet | desktop | large-desktop |
|---|---|---|---|---|
| horizontal | global-scale/200 (16) | global-scale/400 (32) | global-scale/700 (56) | global-scale/700 (56) |
| vertical | global-scale/250 (20) | global-scale/450 (36) | global-scale/500 (40) | global-scale/500 (40) |

## responsive/columns (column-span combinations, resolved px width)
| Token | mobile | tablet | desktop | large-desktop |
|---|---|---|---|---|
| 12m-12t-12d | 328 | 704 | 1168 | 1168 |
| 12m-12t-9d | 328 | 704 | 871 | 871 |
| 12m-12t-8d | 328 | 704 | 772 | 772 |
| 12m-6t-6d | 328 | 344 | 574 | 574 |
| 12m-6t-4d | 328 | 344 | 376 | 376 |
| 12m-6t-3d | 328 | 344 | 277 | 277 |
| mscroll-6t-4d | 280 | 344 | 376 | 376 |
| mscroll-4t-3d | 280 | 224 | 277 | 277 |
| 6m-6t-6d | 160 | 344 | 574 | 574 |
| 6m-6t-4d | 160 | 344 | 376 | 376 |
| 6m-4t-3d | 160 | 224 | 277 | 277 |
| 6m-3t-2d | 160 | 164 | 178 | 178 |
| 4m-3t-2d | 104 | 164 | 178 | 178 |
| 3m-3t-2d | 76 | 164 | 178 | 178 |
| 3m-2t-1d | 76 | 104 | 79 | 79 |
| gutter | 8 | 16 | 20 | 20 |

## responsive/visibility
| Token | mobile | tablet | desktop | large-desktop |
|---|---|---|---|---|
| d0-t0-m1 | True | False | False | False |

## responsive/popup
| Token | mobile | tablet | desktop | large-desktop |
|---|---|---|---|---|
| small | 360 | 480 | 550 | 550 |
| medium | 360 | 688 | 740 | 740 |

## responsive/button
| Token | mobile | tablet | desktop | large-desktop |
|---|---|---|---|---|
| size | medium | large | large | large |
