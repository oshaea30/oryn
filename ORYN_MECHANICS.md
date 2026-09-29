# Mechanical behavior foundation — 2026-09-28

## Scope and honesty

This is deterministic application-owned kinematics, not physics, autonomous
mechanical discovery, a firing-order model, or validated anatomy of a generated
asset. No SDK upgrade, paid generation, new intelligence subsystem or change to
the original drone/V8 ingestion and mapping records is involved.

The generated drone's 39 pieces and generated V8's 200 pieces are **not silently
bound to moving components**. Neither currently has the necessary approved joint,
pivot and geometry bindings. Two separate authored teaching fixtures exercise the
same reusable motion implementation: a 17-part drone and a 27-part V8 mechanism.
They intentionally have no generated-asset hash and cannot overwrite those assets'
annotations/research. The inspector and controls label them authored/unverified.

## Versioned object capability

`OrynMechanicalDefinition` is a JSON-serializable v1 record with stable definition
ID/revision, scope, title, explanation, bounded base frequency, and ordered links.
Each link carries stable component/geometry IDs, parent and driver IDs, subsystem,
home pose, axis/pivot, timing ratio and phase, dimensions/travel, authoring method,
evidence status, reference IDs, and optional verification-record ID.

Motion kinds: fixed, rotation, repeating linear translation, sinusoidal
reciprocation, planar zero-offset slider-crank piston and connecting rod. Parent
expresses assembly ownership; driver determines synchronized timing. Parent is not
an implicit Unity transform parent. Coordinates are assembly-local, with dimensions
in the bound assembly's units. The current fixtures use explicitly authored units.

Provenance (`oryn_authored_benchmark_v1`) is independent of evidence
(`unsupported`, `reference-supported`, `verified`). Authored is not a degree of
proof. All current fixture links are unsupported as factual claims about a real
object. Validation checks structure, finite dimensions, topological order and
required evidence fields; it **does not verify the truth of a citation**. There is
no provider-to-runtime ingestion path that can execute proposed motion.

The pure evaluator emits assembly-local poses from a shared phase. Runtime bindings
apply deltas to geometry children, leaving grab/resize/explode interaction wrappers
alone. Moving touch colliders and outlines follow the rendered geometry. Hidden
parts retain the same clock, so subsystem isolation does not desynchronize them.
Animation during explosion is an inspection illustration: separated/displaced parts
are no longer claimed to be a physically connected mechanism.

The clock supports play/resume, pause, stop/home, bounded speed (0.05–2x), and seek.
App pause/disable pauses playback. Long frame stalls advance at most 0.1 seconds
per rendered update, avoiding a large visual jump; this is not a wall-clock simulator.
No per-frame network, inference, rigidbody solving or material creation is involved.

## Implemented demonstrations

| Fixture | Behavior | Authored assumptions |
| --- | --- | --- |
| Drone | Four rotor/propeller pairs, 1:1 drive, opposed directions, propulsion isolation | Geometry, rotor axes, ratios, directions, illustrative speed; no thrust/flight physics |
| V8 | Shaft/crankpins/webs, eight synchronized rods and pistons, rotating-assembly isolation | Dimensions, 90-degree banks and crank phasing; no claimed engine revision/firing order, combustion, valves or force model |

The regular headset panel gains DRONE DEMO / V8 DEMO, PLAY, PAUSE, STOP/HOME,
SLOW (0.15x), 1x and SYSTEM/ALL. Existing explode/reassemble/manipulation remain
separate. Resetting the whole object also homes its mechanism. The inspector shows
authored part names without saving them as generated-mesh identities.

Unity menu: **Oryn → Mechanics → Open desktop demo**. The local viewer invokes the
same runtime classes and additionally offers a quarter-cycle inspection pause.
Natural-language/voice routing to these new controls is **not implemented yet**.
The command bridge exposes a small read-only mechanical summary but deliberately
does not accept existing generated-asset commands against an unhashed demo.

## Verification and remaining gate

- 233 Python backend tests passed, including reference retrieval/assessment controls.
- Four browser regression suites passed (request, command, geometry evidence, episode).
- Full updated runtime and editor/test assemblies compile with Unity's compiler;
  emitted warnings are in existing sample/development code.
- Exact solver source executed in an isolated Unity 6000.6.3f1 project: **11,576
  checks passed**, covering both banks, four phases, full-cycle linkage closure,
  piston axis constraints, repeatability, linear/reciprocating motion and invalid rods.
- On 2026-09-29, after the user force-quit the stalled editor, the full-project
  batch completed successfully: 1,914 mechanical checks, 284 workspace checks,
  254 menu checks, 29 command checks and 45 synthetic-assembly checks. These include
  isolation, manipulation transforms, explode, home and clock partitioning, but
  are not a substitute for live hand/controller or headset performance tests.
- Exported drone/V8 JSON and rendered captures were inspected. These remain simple,
  unlit teaching fixtures; the V8 side supports obscure some parts until isolated.
- The prior editor log contains repeating native asset-import memory/mutex failures
  and grew to 9,773,081,125 bytes. Root cause is not established. No source assets,
  project cache or old log were deleted; the fresh test process exited successfully.
- ORYN 1.12.0 (Android version code 15) built successfully on 2026-09-29. APK package
  metadata/signature checked; installed as an in-place update on the connected
  Quest 2 and launched. Installed version, live state and hand-grab logs confirmed.
  Build gate now includes the mechanical tests. No app data was cleared.
- Headset motion appearance, performance, collision feel and menu reach still need
  acceptance testing. Installation/startup alone is not a motion-validation pass.
- A guided, user-operated Quest check subsequently observed the authored drone
  selected with playback enabled, speed set to 0.15x, then playback paused. Each
  stage was reported by the live runtime; no automated object commands were sent.
  This validates those control-state transitions, not visible rotation or feel.
- The user then confirmed the drone propellers visibly spun, slowed and stopped
  correctly on Quest. This is user-reported visual acceptance of drone playback;
  it does not establish V8 behavior, motion inference or mechanical truth.
- A subsequent user-operated V8 checklist observed playback enabled, 0.15x speed,
  pause, then resumed playback and a fresh MotionIsolate button event while the V8
  was selected. The terminal in-headset notice was acknowledged. No automatic
  object commands were sent. Rod/piston appearance and actual subsystem visibility
  still require user confirmation; an isolation button event alone is not proof
  that only the intended geometry was hidden.
- The user subsequently confirmed that the V8 crankshaft, rods and pistons moved
  together, slowed and paused correctly, and continued moving when System/All hid
  the supports. This completes user-reported visual acceptance of this authored
  V8 sequence. Combined with the drone confirmation, the bounded headset playback
  checkpoint is complete. It does not verify real-engine anatomy, generated-mesh
  bindings, physical accuracy, broad device performance or every interaction path.
  Pause further subsystem work here for the agreed MVP 1 scope review.

To repeat the completed integration run with the main editor closed, use `-batchmode -executeMethod
Oryn.Editor.OrynMechanicalTests.RunBatch` (no `-quit`; the async runner exits itself).
It runs mechanics and existing workspace/menu/command/assembly tests, exports JSON
definitions, and renders drone/V8 captures into ignored `Builds/Mechanical/`.
Then use the existing workspace Android build path and perform Quest acceptance.

## Safe inference later — not this milestone

Require reviewed piece identities, source scale/frame, joint axes/pivots, constraints,
reference-backed relationships and evidence binding to the exact object/revision.
Treat AI proposals as candidates. Validate units, graph cycles, linkage closure and
supported mechanism class; preview with bounded speed/travel, record corrections,
then explicitly approve geometry bindings. A generic engine reference is not proof
of the generated engine's internals. Keep unsupported links inert.

## MVP scope checkpoint

MVP 1: request → interact → inspect/explain → demonstrate supported behavior.
MVP 2: autonomous investigation and persistent improved understanding.
MVP 3: cross-object generalization, simulation and training.

Shortest impressive demo path: execute full-project tests → inspect captures →
build/install Quest → test play/slow/pause + explode/isolate/manipulate → add bounded
language routing for those existing actions → curate one visually strong asset with
approved motion bindings. Generated-object anatomy and autonomous motion inference
are not prerequisites for an honestly labeled MVP 1 teaching demonstration.

Current blockers are verification/deployment and product integration, not a need
for another cognitive provider or physics engine. Stop here for scope review; do
not add another major intelligence subsystem.
