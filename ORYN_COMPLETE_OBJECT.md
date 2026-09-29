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

## Follow-up checkpoint — feedback and cancellation

- ORYN now publishes ordered thinking/working/answer/failure/cancelled notices to
  an application-owned Quest panel. Delivery is asynchronous and best-effort; a
  display failure never authorizes or repeats a command. Stale, expired and
  out-of-order notices are rejected. Contextual answers hide on selection changes.
- Pending execution receipts are processed by the application without requiring
  the browser to remain open. Receipts now carry the runtime's post-action
  reference token, preventing a late receipt from restoring an obsolete subject.
- Cancel Request atomically stops undispatched work. A provider call already in
  flight may still incur usage; its eventual result cannot execute an action or
  replace a newer browser turn. Dispatched actions are not falsely claimed to be
  undone. Replacement requests still wait for the current provider call to finish;
  full voice interruption and speech cancellation are not implemented.
- Existing journal records retain identity and execution state across the upgrade.
- 264 offline Python tests pass, including cancellation races and ordered feedback
  delivery. Browser cancellation/reload/late-response checks pass. Unity build gates
  pass with 49 Complete Object checks; the feedback panel was rendered and inspected.
- Android 1.13.1/code 17 built and signature-checked. Final APK SHA-256:
  `b231221b9e62aa2c741d560c9c16e9afcd3efdf5070126f4bee25d6d97c86ab5`.
- The final 1.13.1 build installed and launched with app data retained. The final
  package passed installation and startup checks. Quest reported not ready
  for object actions; no object command was sent in this checkpoint.
- The local ORYN service is running with its existing connection and spending
  controls. A proposed single live read-only OpenAI test was rejected by automatic
  approval review pending explicit authorization of the payload and paid call.
  No live provider test ran. Installation is not visual or end-to-end acceptance.

## Approved live interpretation checkpoint — 2026-09-29

After explicit authorization of the payload and one paid call, ORYN's own
conversation service and interpreter completed a read-only live OpenAI test using
the Unity-exported authored drone record with `motor_0` selected. The transport
used a recorded fixture and rejected any attempted command; this was not a live
Quest interaction.

- Question: “What does this motor do?”
- Validated intent: `describe`, target `selected`.
- Application answer: “In this authored model, this motor houses rotor 0, which
  drives propeller 0. The motor housing stays fixed.”
- Result: completed, no action, no retry. Model interpretation took 4,809 ms;
  the test completed in 4.812 seconds.
- Shared ledger settled successfully: conservative usage estimate $0.00621,
  below the approved $0.03 ceiling (not an invoice).
- Evidence retained authored provenance `oryn_authored_benchmark_v1` and
  `unsupported` status for real-object verification. The model chose the intent;
  ORYN resolved the selected component and supplied the authored explanation.

This resolves the earlier approval blocker and proves one live interpretation
case. It does not establish general language quality, headset answer visibility,
command execution or first-minute usability.

Remaining: Quest acceptance, spoken input through this same application path,
full interruption behavior, and polished hero geometry.


## Headset feedback fix — basic propulsion questions

The first user headset session recorded an executed `show_drone` receipt, then two
unsupported-request answers. The user supplied “What makes this drone fly?” as a
reproduction. The interpreter explicitly excluded thrust/flight questions and the
object record contained only drive relationships, so this was a knowledge and
routing gap rather than a disconnected headset. Receipt and feedback acknowledgments
do not establish visual acceptance.

The application now supplies a curated general propulsion explanation, scoped to
the reviewed authored drone revision and its four motor/rotor/propeller chains.
Basic propulsion questions can select that explanation through the existing
`describe` subsystem route. General thrust is sourced to
[NASA Glenn: Propellers](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/propellers/);
the browser presents that source separately from model-specific evidence. Component
identities and flight performance remain unverified. Numerical thrust, payload,
flightworthiness and “make it fly” remain unsupported. No simulation or action is
added by this explanation.

Validated intent is now journaled for diagnosis; question text is not retained.
268 offline Python tests and the mocked conversation browser checks pass; the real
Unity-exported record matches the scoped explanation. No new paid interpretation
was run for this fix. The user must retry the question through ORYN to establish
live interpretation and headset presentation. No APK update is required.
