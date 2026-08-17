# Platform Capability Agent

Answers one question: **"Can this journey be implemented on this platform?"**

Given a platform name and a list of required capabilities, it returns a
structured, sourced verdict — what's supported, what isn't, what's
undocumented, what conflicts, and how confident the answer is.

```bash
python3 cli.py --platform EVA --requirements "authentication,form input,document upload,api call,camera capture"
```

More examples with full output: [`examples/example_runs.md`](examples/example_runs.md).

**Live demo** — narrated walkthrough of 7 realistic HDFC journey questions
(address-change on EVA, the same journey on IVR, an undocumented WhatsApp
channel, a knowledge conflict, a platform pending governance approval...),
run for a live audience:

```bash
python3 demo.py            # paced, ~35s, for showing to people
python3 demo.py --fast     # no pauses
```

Every verdict it prints is computed live against the real knowledge base —
nothing in `demo.py` is pre-scripted output.

---

## 1. Problem definition

A journey ("update my address") can be logically well-formed and still be
impossible to build on a given platform, because that platform's UI/runtime
doesn't expose a capability the journey needs (e.g. native camera capture on a
conversational assistant with no hardware access). Today that mismatch is
usually discovered mid-build. This agent is meant to catch it **before**
journey generation starts, by checking requirements against documented
platform capabilities.

## 2. Agent responsibility

The agent does exactly one thing: compare a set of required capabilities
against what a named platform is documented to support, and report the result
with evidence. It does **not** decide what a journey requires (that's a
journey-planning concern, upstream of this agent) and it does **not** generate
UI or code (that's downstream). This keeps it a single, testable unit that
other agents in a larger pipeline can call.

```
Journey Planning → Journey Requirements → [ Platform Capability Agent ] → Yes/No + why
```

## 3. Input / output schema

Defined in [`agent/schema.py`](agent/schema.py).

**Input** (`CapabilityRequest`):

```json
{ "platform": "EVA", "required_capabilities": ["authentication", "form input", "document upload"] }
```

Capability names are free-text tolerant — `"form input"`, `"form_input"`, and
`"forms"` all resolve to the same canonical ID (see §5).

**Output** (`AgentResponse`):

| Field | Meaning |
|---|---|
| `platform` | Normalized platform ID |
| `status` | `fully_supported` \| `partially_supported` \| `not_supported` \| `unknown_platform` \| `platform_pending_approval` \| `insufficient_knowledge` |
| `supported` | `true` only when `status == fully_supported` |
| `requested_capabilities` | Normalized, deduplicated input |
| `supported_capabilities` / `unsupported_capabilities` | Unambiguous verdicts |
| `capabilities_needing_investigation` | Requested but not documented anywhere for this platform |
| `conflicts` | Capabilities where knowledge documents disagree, with both source files named |
| `constraints` | Free-text constraints relevant to the requested capabilities |
| `knowledge_sources` | Exact files that informed this answer |
| `confidence` | 0–1, see §7 |
| `reasoning` | Human-readable trace, one line per capability decision |

This is a superset of the two example schemas in the brief — `status` and
`conflicts` were added because the brief's own test-case list (unknown
platform, insufficient knowledge, conflicting knowledge) needs a way to
distinguish those three outcomes from a plain "supported: false", and
`conflicts` needs somewhere to carry both source files rather than silently
picking one.

`platform_pending_approval` is a fourth, narrower case than `unknown_platform`:
a knowledge document exists for the platform but hasn't cleared governance
(`status != approved`). That distinction matters to a caller — "onboard a new
platform" and "chase down a pending approval" are different follow-up actions
— so it's a separate `status` value rather than being folded into
`unknown_platform` with the difference only visible in `reasoning` text.

## 4. Knowledge structure

One markdown file per platform (or several, if a platform has multiple
sources — see §9) in `knowledge/`, using a fixed section convention:

```markdown
---
platform: EVA
platform_full_name: Enterprise Virtual Assistant
---

## Supported Capabilities
- `authentication`: Supports OTP-based authentication via the platform's auth component.

## Unsupported Capabilities
- `native_camera_capture`: EVA cannot invoke the device camera directly.

## Constraints
- `document_upload`: Must use the platform's supported attachment component.

## Notes
Free text, not parsed structurally.
```

Why structured markdown instead of free prose: the file is still human-editable
(a platform owner can update it without touching code), but the capability ID
in backticks gives the loader an exact key to index on, rather than having to
infer meaning from prose. See [`agent/knowledge_loader.py`](agent/knowledge_loader.py)
for the full convention and parser.

## 5. Retrieval approach

**Not** vector/semantic search. Retrieval is exact-match lookup: normalize the
platform name and each capability name to canonical IDs
([`agent/normalize.py`](agent/normalize.py)), then look them up directly in an
index built once at load time from all markdown files.

This is a deliberate choice for this problem, not a simplification:

- The questions this agent answers are precise ("does X support Y?"), not
  fuzzy/exploratory — exact lookup is the correct tool, not an approximation.
- Every answer must be traceable to an exact file (`knowledge_sources`).
  Similarity search over chunks makes that traceability fuzzy; exact-key
  lookup makes it exact by construction.
- It's fully deterministic, so the same input always produces the same
  output — required for something a journey validator will call
  programmatically and trust.

## 6. Agent reasoning

Per required capability, against the resolved platform's knowledge:

1. **In both** the supported and unsupported lists (from different files) →
   **conflict**. Not resolved automatically or silently — surfaced with both
   source files, `status` degrades to `insufficient_knowledge`.
2. **Only in supported** → resolved supported.
3. **Only in unsupported** → resolved unsupported.
4. **In neither** → `capabilities_needing_investigation`. This is the core
   anti-hallucination rule: absence of documentation is never treated as
   evidence of support *or* non-support.

Overall `status` then follows directly from those four buckets (see
`_classify` in [`agent/capability_agent.py`](agent/capability_agent.py)):
conflicts or undocumented capabilities → `insufficient_knowledge`; mixed
resolved supported/unsupported → `partially_supported`; all unsupported →
`not_supported`; all supported → `fully_supported`.

**No LLM is in this decision path.** See the module docstring in
`capability_agent.py` for the full rationale — in short, an LLM reasoning over
retrieved text can still fill a gap with plausible pretrained knowledge, which
is exactly the failure mode the brief explicitly rules out ("should not invent
capabilities when knowledge is unavailable"). A deterministic lookup structurally
cannot do that. An LLM is still a reasonable *addition* on top — e.g. turning
`reasoning` into a friendlier sentence for a human, or helping a journey
planner turn "update my address" into a `required_capabilities` list in the
first place — but neither of those is allowed to change what counts as
"supported," so neither is part of this agent's decision.

## 7. Validation

- `required_capabilities` must be non-empty — the agent raises rather than
  guessing what was meant (see `evaluate()` in `capability_agent.py`).
- Unknown platforms are never partially answered — every requested capability
  goes to `capabilities_needing_investigation`, `confidence` is `0.0`, and
  `reasoning` names the platforms that *are* known, so the caller has a next
  step.
- `confidence` is computed from how much of the requested set was resolved
  unambiguously, penalized more heavily for conflicts than for gaps (a
  contradiction means the knowledge base itself needs fixing, which is worse
  than it simply being incomplete):

  ```
  confidence = (resolved / total) − (conflicts × 0.5 + undocumented × 0.3) / total
  ```

  Confirming that a platform supports **nothing** requested still yields
  `confidence: 1.0` if every capability was unambiguously documented as
  unsupported — confidence reflects certainty of the verdict, not how
  favorable it is.

## 8. Failure handling

| Situation | Behavior |
|---|---|
| Platform not in knowledge base at all | `status: unknown_platform`, `confidence: 0.0`, no capability is marked supported or unsupported |
| Platform's knowledge document exists but isn't `status: approved` | `status: platform_pending_approval` (not `unknown_platform`), `reasoning` names the pending document; the two `get_platform_capabilities`/`check_supported_component` tools return `ok: false, error.code: not_retrievable` rather than silently treating it as retrievable |
| Capability never mentioned for a known, approved platform | Goes to `capabilities_needing_investigation`, not silently dropped or assumed |
| Two approved files disagree on a capability | Surfaced in `conflicts` with both file names; overall status degrades; `higher_authority_source` is an informational hint only (explicit `supersedes` wins if declared, else `authority_rank`) — never used to auto-resolve |
| Malformed knowledge file (missing `platform:` frontmatter, or a Supported/Unsupported bullet missing its backticked capability id) | Loader raises `ValueError` at load time, naming the file and the offending content — fails loudly rather than silently skipping bad data |
| Empty requirements list | `evaluate()` raises `ValueError` rather than returning an empty/meaningless result |

## 9. Test cases

All six scenarios from the brief are implemented as automated tests in
[`tests/test_agent.py`](tests/test_agent.py), run with:

```bash
python3 -m unittest discover -s tests -v
```

| # | Scenario | Platform / requirements used |
|---|---|---|
| 1 | Platform supports everything | EVA: authentication, form_input, document_upload, api_action |
| 2 | Platform supports only some | EVA: same + camera capture |
| 3 | Platform supports none | IVR: form_input, document_upload, native_camera_capture |
| 4 | Platform unknown | `WHATSAPP_BOT` (no knowledge file exists) |
| 5 | Insufficient knowledge | EVA: authentication + `biometric_liveness_check` (undocumented) |
| 6 | Conflicting knowledge docs | `LEGACY_PORTAL`, which ships two knowledge files that disagree on `document_upload` (see `knowledge/legacy-portal-platform-capabilities*.md`) |

Plus a 7th scenario the brief's list doesn't name explicitly but the metadata
contract implies — a platform that's documented but governance-pending
(`NEW_PORTAL`, `status: draft` — see `knowledge/new-portal-platform-capabilities.md`),
which must be distinguishable from a fully unknown platform.

Also covered: alias normalization, platform-name case/whitespace
insensitivity, the empty-input guard, a JSON-serializability check, that a
malformed capability bullet fails loudly instead of silently vanishing from
the index, and that the conflict-authority hint follows an explicit
`supersedes` declaration even when it disagrees with `authority_rank` — 14
tests total, all passing.

## 10. Final working example

The brief's own example, run for real against the sample knowledge base:

```bash
python3 cli.py --platform EVA --requirements "authentication,form input,document upload,api call,camera capture"
```

returns `status: partially_supported`, four supported capabilities, one
unsupported (`native_camera_capture`), the exact constraint text about the
attachment component, and `confidence: 1.0` because every requested capability
was unambiguously documented. Full output in
[`examples/example_runs.md`](examples/example_runs.md#2-platform-supports-only-some-requirements-the-briefs-own-example).

---

## Project layout

```
platform-capability-agent/
├── agent/
│   ├── schema.py            # CapabilityRequest / AgentResponse / Conflict dataclasses
│   ├── normalize.py         # free-text → canonical ID normalization
│   ├── knowledge_loader.py  # markdown → structured PlatformKnowledge index
│   └── capability_agent.py  # the agent itself (evaluate())
├── knowledge/                # sample platform capability docs (edit/add freely)
├── tests/test_agent.py       # the 6 required scenarios + extras
├── examples/example_runs.md  # real captured output for every scenario
├── cli.py                    # command-line entry point
├── demo.py                   # narrated live-demo script (7 scenarios, paced)
└── README.md
```

## Extending this to a new platform

Drop a new markdown file in `knowledge/` following the convention in §4 — no
code changes needed. To reuse this pattern for a **different** capability-style
agent entirely (e.g. "can this API endpoint handle this request shape?"), the
reusable parts are `normalize.py`'s pattern (free text → canonical ID) and
`capability_agent.py`'s four-bucket classification (`resolved-yes` /
`resolved-no` / `conflict` / `undocumented`) — swap out what "capability" means
and what the markdown describes, and the same reasoning shape applies.
