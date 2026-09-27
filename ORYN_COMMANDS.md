# ORYN command lab — 1.10.0

This milestone is **text intent → saved record lookup → confirmed runtime action**.
It is not component recognition, schematic retrieval, a general conversational agent,
or an OpenAI-versus-Gemini quality verdict. No provider is selected as the winner.

## Run

From this repository:

```sh
/opt/homebrew/bin/python3 Orchestrator/command_app.py
```

Open http://127.0.0.1:8767/ with one authorized Quest connected over USB and ORYN
open. This service is separate from generation on port 8765 and the island preview
on 8766. Do not restart generation to start commands.

1. Refresh from Quest. Release held objects and finish any prayer gesture.
2. Select a geometric part in the headset, then ask “What is this?”
3. Try “Isolate this”; review the response and explicitly confirm the action.
4. Check the receipt: only **executed** means Unity applied it.
5. “Put it back together” proposes reassembly. “Explode” proposes full spread.
6. “Find the battery” searches exact case-insensitive saved user labels. Missing
   or duplicate labels produce an explanation, not an inferred component identity.

The default interpreter is an **offline exact-phrase test**, not AI. It exercises
the real saved knowledge and USB action path without charges. The interface lists
the supported phrases. A model provider accepts broader wording within the same
small intent contract; it does not generate object facts in this milestone.

## Optional model providers

See [ORYN_SPENDING.md](ORYN_SPENDING.md) for the persistent spending policy.
Offline remains the default. For paid tests, choose OpenAI and a reviewed profile,
expand configuration, and save the API key/profile in process memory. Routine
defaults to GPT-6 Sol/medium. Benchmark explicitly selects Astra. Arbitrary model
IDs and unpriced Gemini generation are no longer offered as paid routes.

Click “Send text for token-count quote” to share this bounded request with the
provider's counting endpoint. Review the exact input count, maximum output, maximum
cost and daily remaining allowance. Then approve that exact quote and interpret.
Quotes expire after 120 seconds and are invalidated by changes to input, context,
credentials or policy. Every generation first reserves its maximum in SQLite.

The request sends its question and bounded part IDs, labels, status and revision;
never GLB, room image, file path, voice or annotation history. Keys are not persisted
in the browser, ledger, project or headset. OpenAI uses `store: false` and Standard
processing; provider data handling still follows its terms. No automatic retry or
escalation occurs. Restarting clears keys, not usage history or unresolved costs.

Both adapters receive the same instructions, context shape and intent schema.
Only `{intent, target, label}` is accepted. ORYN resolves IDs, composes grounded
responses and validates all actions itself. Compare each provider using the same
fixture/selection and prompts; do not apply actions between comparison requests.
Suggested cases: selected labeled part, selected unidentified part, absent battery,
duplicate motor labels, isolate, reassemble, negation, multiple actions and a
request for an unknown functional relationship.

Official API contracts consulted for these adapters:

- [OpenAI structured outputs / Responses](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Gemini Generate Content structured outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)

Live provider compatibility, latency, accuracy and cost remain **unverified until
credentials/model IDs are configured and explicit paid tests are run**. Unit tests
use fake credentials and responses; they do not establish live model performance.

## Trust and command boundary

The headset writes `CommandBridge/state.json` in app-specific storage. It includes
an app-session UUID, context token, heartbeat and selected assembly instance.
Context includes saved record revisions and reports unreadable records explicitly.
The Mac rejects stale snapshots. Both sides require a ready, focused workspace.

Each confirmed command binds to that exact session/context, expires after 30 seconds,
and can only select, isolate, explode or reassemble. Changes to selection, labels,
assembly or readiness invalidate the context. No relabeling, deletion, generation,
arbitrary Unity method calls or shell strings can be supplied by the model/browser.

The Mac publishes via a temporary file followed by atomic rename. Unity validates
again, writes a durable **uncertain/claimed** receipt before touching the scene,
then writes **executed** or **rejected**. A claimed UUID is never replayed. If Unity
crashes between claiming and completion, inspect the scene; do not assume success.
Transport failures also never resend automatically. Rejected/expired requests need
a new explicit question and confirmation. Labels and model caches are not edited.

This is a trusted-local-user USB prototype, not a production authenticated device
protocol. ADB authorization grants powerful device access. The console binds only
127.0.0.1, checks exact Host and same-origin/CSRF token on POST, has no CORS, uses a
restrictive CSP, renders data with textContent, and does not log requests/keys.
Its credentials and in-memory command results disappear on process exit. Paid
usage IDs, reservations and cost metadata persist separately in the ledger.
Command results are bounded at 500 per process. Durable Quest receipts remain
for replay protection.

## Validation

```sh
/opt/homebrew/bin/python3 -m unittest discover -s Orchestrator -p 'test_*.py' -v
/opt/homebrew/bin/node --check Orchestrator/command.js
```

`OrynRuntimeModelTests.ValidateAndBuild` also runs `OrynCommandTests`: allowlist,
target validation, stale context/session, focus/held gate, expiry and ID binding.
Existing assembly, gesture, annotation, recovery and menu tests are retained.

Verified for this milestone: 68 Python tests, 1,052 Unity checks, signed Android
build 1.10.0 (code 13), and installation on the connected Quest. The optional
`Orchestrator/check_command_ui.cjs` Playwright/Chrome regression checks provider
choices, action confirmation, receipts, consent reset, text escaping and mobile
layout using mocked API routes only.

Live USB checks read 39 geometric parts and the saved Part 4 “Other” annotation
(revision 1). “What is this?” returned that annotation with its unverified status;
“Find the battery” declined to invent an identity. The headset issued executed
receipts for isolate and reassemble. A separate reassembly attempt was rejected
when a grab started between proposal and execution. Final verified state was whole
assembly mode, not isolated, with the saved label unchanged. No paid provider calls
were made.

Next: run identical paid provider evaluations, then extend evidence-backed
explanations and relationships. Voice can feed this same validated text boundary.
