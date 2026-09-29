# Complete ORYN Object v1

MVP 1 reference implementation: the authored drone. ORYN owns interpretation,
reference resolution, knowledge lookup, execution validation and receipts. Codex
is a development tool, never a runtime controller or source of live answers.

## Object contract

An object declares a stable definition ID and revision, a session instance ID,
visual geometry bindings, selectable component IDs, subsystem membership,
authored relationships, bounded explanations, evidence/provenance and supported
actions. Runtime identity is separate from generated-asset hashes. Authored
objects must never read or write generated-mesh annotations under a fabricated hash.

Authored descriptions explain what the demonstration represents. They are not
verified facts about a real product. Evidence status and authoring provenance are
independent. A runnable motion is not evidence of physical accuracy.

The initial implementation exports the current authored drone directly from its
validated mechanical definition and explicit geometry bindings. The application
interpreter can select only declared actions and targets; it cannot generate code,
write knowledge, introduce component identities or author unsupported explanations.
Unknown requests stay unknown. Open-ended generation stays at /objects during this
increment, so an unrecognized command never accidentally purchases geometry.

## Application contract

Typed input and eventual voice transcripts use the same conversation endpoint.
The existing OpenAI connection and shared persistent cognition budget supply the
interpreter. The application resolves selected and previous references, produces
answers from object records, and sends commands itself. There is no Codex callback.
The offline interpreter is explicitly a test fixture, never a production fallback.

Capture object instance/revision and visible selection before interpretation.
Check fresh context before displaying an answer or sending an action. Follow-up
references expire on object/selection changes. Store the last explained/action
subject for “why these?” and “show me”; do not infer it from arbitrary chat text.
Record requests before paid calls or command transfer. Reusing an ID cannot bill or
execute again, including after restart. Uncertain requests are never retried.

## First increment and remaining acceptance

The first increment is the typed application-owned route: show the authored drone,
select/describe components, explain relationships, demonstrate, play/pause/slow,
isolate, explode and restore. “Reassemble” restores assembly layout and keeps
playback; “restore/reset” also stops motion, homes the mechanism and restores 1x.
Ordinary actions need no confirmation dialogs. Busy/unfocused Quest actions fail
without being queued for surprise execution later; read-only questions can use a
selected held component. Transfer is pending until a Quest receipt confirms execution.

Voice, cancellation/interruption, polished geometry, in-headset conversational
feedback and uncoached first-minute/five-minute acceptance remain milestone gates.
This first typed increment is not completion of the full MVP.

Acceptance must include altered request order, changed selections during model
latency, duplicate submissions, unavailable provider/headset, unsupported claims,
“why these?”, “show me”, and recovery. No new provider, cloud migration, automatic
motion inference, simulation or generalized object research is part of this work.

## Verification checkpoint — 2026-09-29

- 256 Python tests pass with paid providers mocked, including shared-ledger
  reservation/settlement, HTTP authentication, changed-selection rejection,
  duplicate/restarted request protection and grounded follow-up resolution.
- Unity mechanical/interaction/command suites pass. The 38 new Complete Object
  checks cover stable bindings, focused motor/propeller demonstrations, capability
  gates, stale contexts and acquisition from an empty workspace.
- The actual Unity-exported 17-component record passes the Python contract validator.
- Conversation and existing object-request browser regressions use mocked routes.
- Android 1.13.0 / code 16 built successfully; package metadata and signature checked.
  APK SHA-256: `f6425b3877b043277027ae0d5047a018547463d55740ba5f92f81e26daab1d0b`.
- This pass did not install the APK, exercise the live provider or operate Quest.
  Therefore end-to-end language accuracy, measured hardware latency and usability
  are not claimed. Voice, interruptions and polished geometry remain unimplemented.

Run `python3 Orchestrator/app.py` and open `http://127.0.0.1:8765/` for the typed
route after installing the matching APK. The existing OpenAI research connection
supplies the key and shared budget; `/objects` retains connection settings and
other object requests. There is no offline production fallback or automatic paid
retry. The developer command lab at port 8767 keeps its existing diagnostic gates.
