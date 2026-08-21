# 05 — Typography (full token values)

Depends on: 01-Primitives (Primitive-type), 03-Semantics (`text/family`).
8 confirmed roles, each bundling family + weight + size + line-height +
letter-spacing.

| Token | Family | Weight | Size | Line-height | Letter-spacing |
|---|---|---|---|---|---|
| typography.display.balance | text/family *(brand-resolved)* | bold-700 | font/size/display/lg (48px) | font/line-height/display/lg (56px) | -2% |
| typography.heading.page-title | text/family | semibold-600 | font/size/heading/h1 (36px) | font/line-height/heading/h1 (44px) | -1% |
| typography.heading.section-title | text/family | semibold-600 | font/size/heading/h3 (28px) | font/line-height/heading/h3 (36px) | -1% |
| typography.heading.card-title | text/family | medium-500 | font/size/heading/h5 (20px) | font/line-height/heading/h5 (28px) | 0 |
| typography.body.default | text/family | regular-400 | font/size/paragraph/md (16px) | font/line-height/paragraph/md (20px) | 0 |
| typography.body.subtle | text/family | regular-400 | font/size/paragraph/sm (14px) | font/line-height/paragraph/sm (18px) | 0 |
| typography.caption | text/family | regular-400 | font/size/paragraph/xsm (12px) | font/line-height/paragraph/xsm (16px) | 0 |
| typography.label | text/family | medium-500 | font/size/paragraph/sm (14px) | font/line-height/paragraph/sm (18px) | 0 |

## Brand family resolution
Every role's family resolves through `text/family` (Semantics), which is
brand-dependent: HDFC → Inter, EVA_MB/EVA_DBU → Poppins. No role hardcodes a
literal family name — switching brands automatically switches every role.
See `skills/brand-theming/SKILL.md`.
