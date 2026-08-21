# Intent Recognition Agent

The first node of the Journey Generation pipeline. It reads one natural-language
utterance and produces a structured, gated `AcceptedIntent` that the Journey
Planner consumes directly.

```
User utterance
  → Intent Recognition Agent   (LLM: proposes a hypothesis)
  → Intent Gate                (code: decides accept / reject)
  → Decision Router            (code: continue / clarify / escalate)
  → Knowledge Retrieval → Journey Planner → Generator → Validator
```

It is **not** a chatbot. It never answers the customer and never produces
customer-facing text. Its only output is an interpretation artifact.

---

## 1. The core split: propose vs. decide

This is the whole design, and everything else follows from it.

| | Written by | Type | Meaning |
|---|---|---|---|
| `intent.proposal` | **LLM** | `IntentProposalOutput` | *"I think they want X"* — a hypothesis |
| `intent.accepted` | **Gate (code)** | `AcceptedIntent` | *"The workflow may proceed with X"* — a decision |

An LLM that both interprets *and* approves its own interpretation can be
confidently wrong with nothing to catch it. So acceptance is not a
model-reachable operation: it lives in `orchestrator/intent_gate.py`, uses no
LLM, and is a pure function of the proposal plus frozen config.

The agent's forbidden capabilities are refused by construction, not by
documentation — `accept_intent()`, `route()`, `escalate()`, `merge_into_state()`,
`retrieve()`, `search_knowledge()`, and `answer_customer()` all raise
`IntentBoundaryError`. There is a test for each.

## 2. Acceptance criteria (in evaluation order)

1. Artifact is structurally valid
2. `user_intent` is a member of the intent registry — **closed world**
3. No unresolved ambiguities
4. `platform` is derivable from `channel_hint`
5. Model confidence clears the floor

**Confidence is last on purpose.** Registry membership is an authoritative fact;
model confidence is a self-report, and a model can be confidently wrong. The
floor is a coarse backstop, not the gate.

The gate **accumulates** all failing reasons rather than short-circuiting, so a
human operator sees every problem at once and the Router can apply its
structural-beats-clarifiable precedence over the full set.

## 3. Fields the model does not get to decide

| Field | Derived from | Why |
|---|---|---|
| `platform` | `channel_hint` → `DEFAULT_CHANNEL_PLATFORM_MAP` | The arrival channel is a fact; the model's `platform_hint` is advisory and gets overridden |
| `journey_type` | intent registry | Registry is authoritative for the intent's classification |
| `product_domain` | intent registry | Same |
| `priority` | config | Priority is a business policy, not a reading of the sentence |
| `entities` | filtered to registry-registered types | Blocks invented entities like `approval_granted` |

Every override is recorded in `IntentGateResult.overrides` with the model's
value, the accepted value, and the reason — so an accepted intent is fully
explainable after the fact.

## 4. Ambiguity is a success state

If the utterance is `"change my card"` — block it? replace it? change the limit?
— the correct behaviour is to declare ambiguity, not to pick the closest match.
The prompt says this explicitly, the validator enforces honesty rules against it
(you cannot report confidence > 0.9 alongside unresolved ambiguities, or > 0.5
on `UNKNOWN`), and the gate treats any ambiguity as a hard blocker.

Silently guessing is the worst available failure mode in a banking context, so
the architecture makes guessing more expensive than admitting uncertainty.

## 5. Routing

| Condition | Route |
|---|---|
| Gate accepted | **CONTINUE** → knowledge retrieval |
| Ambiguous / UNKNOWN / low confidence | **CLARIFY** (once) → then escalate |
| Intent not allowlisted, platform underivable, invalid artifact | **ESCALATE** immediately |
| Retriable agent failure | **CLARIFY** (one retry) → then escalate |
| Budget exhausted | **ESCALATE** |

The Intent stage's "repair" is a *clarification* rather than a model retry:
re-running the same model on the same input produces the same proposal. The fix
for an ambiguous utterance is more information from the human, not another guess.
Structural failures escalate immediately because no question to the customer can
make an unsupported intent supported. Budget is hard-capped at one.

## 6. Prompt injection

The utterance is untrusted data. Defence is layered so that no single failure is
fatal:

- The system prompt names the attack and instructs interpretation, never obedience
- The user-message wrapper repeats the boundary adjacent to the untrusted text
- The closed vocabulary means an injected intent id cannot be created
- The gate re-checks registry membership regardless of what the model emits
- Entity types are filtered; control characters are rejected; card-like digit runs are masked
- Acceptance is not a model-reachable operation, so "mark this as accepted" has nothing to act on

`tests/test_adversarial_intent.py` runs five injection payloads through the full
stage and asserts none produce an accepted invented intent.

## 7. Extensibility

Adding a supported intent is a **data change** in
`contracts/intent_registry.py` — no change to the agent, the prompt, the gate,
or the router. This mirrors the knowledge-layer principle that new Markdown
expands capability without a new agent implementation.

## 8. Layout

```
src/hdfc_journey/
  contracts/
    intent.py                  # IntentInput, IntentProposalOutput, IntentGateResult
    intent_enums.py            # status/verdict/override enums, normalize_intent_id
    intent_registry.py         # allowlisted intents (config-as-data)
    intent_validation.py       # 4-layer deterministic validation
    intent_state_mapping.py    # write-permission map + state patches
  agents/intent/
    agent.py                   # proposer + boundary refusals
    prompts.py                 # versioned system prompt
    errors.py
  llm/
    deterministic_intent.py    # reproducible LLM stand-in (offline tests)
  orchestrator/
    intent_gate.py             # THE acceptance authority
    intent_router.py           # continue / clarify / escalate
    intent.py                  # stage runner; owns all state mutation
```

## 9. Running

```bash
pip install -e ".[dev]"
pytest tests/ -q                              # 197 tests
pytest tests/ -q -k intent                    # intent slice only
PYTHONPATH=src:. python3 examples/run_intent_demo.py
```

Configuration is env-overridable: `HDFC_LLM_PROVIDER`, `HDFC_LLM_MODEL`,
`HDFC_INTENT_PROMPT_VERSION`, `HDFC_INTENT_ENFORCE_CONTRACT`.

## 10. Handoff to the Planner

The gate emits `AcceptedIntent` — imported from `contracts/planner.py`, not
redeclared — so `PlannerInput` consumes it with zero glue.
`tests/test_e2e_intent_to_planner.py` runs a raw sentence through intent → gate
→ planner and asserts a journey plan comes out, plus that planning *cannot* run
on a rejected intent.

## 11. Known limitations

- `llm/deterministic_intent.py` is naive keyword matching. It exists to make the
  surrounding machinery testable offline and is **not** a production classifier;
  the real path uses the LLM via `StructuredLLMClient`.
- Multi-turn conversational clarification is modelled
  (`IntentClarificationContext`) but the human-answer round trip is not wired —
  the clarify branch currently re-proposes and then escalates.
- Voice modality is accepted in the contract but no transcription is performed;
  upstream is expected to supply text.
- The channel→platform map lives in code as a module constant. It should move to
  the run config snapshot when a second deployment needs a different mapping.
