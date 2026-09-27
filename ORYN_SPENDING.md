# Persistent development spending controls

Scope: the command console on port 8767, not Meshy on 8765, the Codex application,
other programs using the same key, or a deployed subscription service. No provider
account settings were changed. No paid request or live token-count request was
made to validate this implementation; external responses in tests are mocked.

## Policy

| Profile | OpenAI model | Reasoning | USD ceiling per generation |
|---|---|---|---|
| routine (default paid profile) | gpt-6-sol | medium | $0.03 |
| question | gpt-6-sol | medium | $0.05 |
| question_high | gpt-6-sol | high | $0.05 |
| benchmark | gpt-6-astra | medium | $0.10 |
| benchmark_high | gpt-6-astra | high | $0.10 |

The interpreter remains offline until deliberately configured. These profiles all
use the current narrow intent contract; they do not add schematic retrieval or
general object question answering. No automatic upgrade, retry, agent loop, built-in
tools, voice or generation API other than text Responses is enabled. Gemini's
adapter remains available in source, but paid Gemini requests are blocked until a
reviewed pricing/counting/usage policy is added.

Daily limit: $2, resetting at UTC midnight for completed admissions. Uncertain
and in-flight reservations from previous days continue consuming available funds.
Both the server-owned `developer` identity and global ledger total are checked.
Future authenticated account IDs belong here; the client cannot choose its identity.

## Exact quote → approval → reserve → dispatch → settle

1. A user explicitly asks to send a request for token counting. The count endpoint
   receives the same model, input, structured-output schema and reasoning settings
   as generation. Generation-only settings are not sent to the counting endpoint.
   This step does not invoke generation; if counting fails, there is no heuristic
   fallback and no generation. It still shares the request data with OpenAI.
2. Inputs over 16,000 tokens are refused, well below long-context pricing thresholds.
   Output including reasoning is capped at 1,024 tokens. Provider processing is
   pinned to `service_tier: default` (Standard), not an account-selected premium tier.
3. Worst-case USD cost is calculated using integer nanodollars. Every input token
   is reserved at the most expensive reviewed input category (cache-write rate),
   and all 1,024 possible output tokens are reserved. No cache discount is assumed.
   There are no billable tools enabled. The profile ceiling must cover this amount.
4. An opaque quote ID is bound by SHA-256 to the entire request, policy, actor,
   credential revision, Quest serial, session and context. The approval must name
   that ID and the exact quoted amount. Quotes expire after 120 seconds or pricing
   review expiry, whichever comes first. No amount is accepted as policy from UI.
5. Before the generation HTTP call, SQLite `BEGIN IMMEDIATE` atomically verifies
   identity, quote, expiry, replay status and both budgets, then durably records the
   full reservation with `synchronous=FULL`. Multiple processes sharing this file
   cannot each spend the same remaining budget. A claimed request is never resent.
6. Valid reported input/output usage produces a conservative calculated cost,
   releasing only the unused reservation. Input tokens are still priced at the
   worst reviewed input category, not an assumed cache hit. Refusal or incomplete
   output can consume tokens and is accounted for even though it produces no action.
7. A network failure/timeout keeps the full reservation. A crash leaves `reserved`
   state, which is also fully counted. Missing/inconsistent usage, unexpected model
   version, tier or output types keep the reservation and halt future paid calls.
   No automatic reconciliation, refund, reset or retry is provided.

`calculated_cost_nanos` is a usage-derived upper bound under the reviewed rate
policy, **not the provider invoice**. `actual_cost_nanos` remains NULL until a
future evidence-backed invoice reconciliation workflow exists. Account-specific
contracts, taxes, changed provider pricing or provider billing errors are outside
this local calculator's guarantee. Provider-side enforced limits remain a separate
backup to configure before wider deployment.

## Reviewed prices and expiry

Reviewed 2026-09-27, expires **2026-10-04 00:00 UTC**. Startup does not silently
renew that review. After expiry, offline continues and paid requests are blocked
until the pricing policy is deliberately reviewed and updated.

Standard USD per million tokens:

| Model | Input | Cached input | Cache write | Output |
|---|---:|---:|---:|---:|
| Sol | 2 | 0.20 | 2.50 | 10 |
| Astra | 10 | 1 | 12.50 | 50 |

Sources used with the OpenAI Docs skill:

- [Sol model rates and supported reasoning](https://developers.openai.com/api/docs/models/gpt-6-sol)
- [Astra model rates and supported reasoning](https://developers.openai.com/api/docs/models/gpt-6-astra)
- [Exact token counting](https://developers.openai.com/api/docs/guides/token-counting)
- [Count endpoint contract](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count)

## Storage, restart and recovery

Default ledger: `.oryn-usage/usage.sqlite3`, ignored by Git. The directory is created
0700, DB file 0600. It stores request/actor/provider/model/profile/operation IDs,
fingerprints, pricing version, token counts, reservation, calculated cost, nullable
invoice amount, status and timestamps. It stores no credentials, raw questions,
part labels, raw provider responses or Quest imagery.

Credentials and full request bodies stay in memory. After restart, old quotes
cannot run; new quotes must be explicitly prepared. Used IDs and unresolved money
remain durable. Corrupt/unavailable/unknown-schema ledgers and backward clock
movement block paid activity. Never delete/reset the ledger to clear a budget.

For an uncertain request or circuit-breaker halt: inspect the provider's usage
records against the locally recorded request time/model and retain the reservation
unless evidence establishes the charge. There is intentionally no browser button
that can clear this safety state. Back up the database before any future audited
reconciliation. Losing/deleting the entire ledger loses its accounting history;
production requires managed durable storage, backups and authenticated operations.

This is single-host SQLite coordination, not a multi-region billing platform.
A cloud deployment should keep the same admission contract using a shared
transactional database, authenticated account identities, idempotency keys,
production rate limits and append-only reconciliation audit records.

## Validation

```sh
/opt/homebrew/bin/python3 -m unittest discover -s Orchestrator -p 'test_*.py'
/opt/homebrew/bin/node --check Orchestrator/command.js
```

`check_command_ui.cjs` additionally covers quote display, changed-input
invalidation, exact approved amount, one-use approval, Gemini blocking and mobile
layout using mocked HTTP responses. The Python tests cover concurrent processes,
restart persistence, duplicate IDs, midnight carryover, expiry, changed context,
timeout and corruption. Live provider API compatibility is not claimed by mocks.

Implementation verification (2026-09-27): 86 Python tests passed, JavaScript syntax
check passed, and the browser regression passed. The live console was restarted
with the same ledger and displayed $0 charged/reserved, $2 available, offline mode.
No Unity rebuild was needed; headset controls and generation service were untouched.
