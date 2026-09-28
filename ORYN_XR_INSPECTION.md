# Read-only XR Operator inspection

## Headset-guided tests (ORYN 1.11.0 development build)

`OrynTestGuide` is attached only in Editor/development builds. It displays a small
head-relative status panel above the central view, with no collider or input target.
Ready/testing instructions, terminal results and a short completion/blocked tone
remove the need to read chat while wearing the headset. It is not a production
dependency and never changes object state itself.

```sh
node Orchestrator/xr_guided_test.cjs --execute --asset-sha256 <prepared-asset-sha256>
node --test Orchestrator/test_xr_guided.cjs Orchestrator/test_xr_assembly.cjs
```

The runner waits up to five minutes for an active app, then up to five minutes for
the exact 39-part asset to be whole-selected, assembled and ready. Five continuous
seconds of hands-off readiness trigger one existing guarded explode/reassemble
cycle. Selection/readiness changes reset the countdown. The selected owner number
is discovered only after checksum matching; an older similar drone cannot substitute.
App/device session changes stop the run. No generation or language-model calls occur.

Display notices use separate `CommandBridge/test-status.json` / `.ack` files;
schema, run ID, app session, monotonic sequence, phase, size and short expiry are
validated. Only controlled display phases are accepted. Display acknowledgement is
required before starting and before each action. A heartbeat keeps progress current.
If the heartbeat stops, an active ready/testing panel becomes BLOCKED locally when
the app updates again; it never manufactures a pass. Terminal results remain visible
for the app session. A failed display/ack blocks further action rather than silently
running tests. Physical focus and command context are still independently validated
by Unity's existing command bridge.

Results go to `.oryn-inspection/guided-*/report.json`. Scope remains command-level
transforms, not gesture quality, visual perception, semantics or verified mechanics.
These tests do not prevent the user from interacting; grabbing during the test may
stop it. They do not keep the headset awake or override focus. An expired/stopped run
must be armed again from the Mac; it does not silently resume later.

The 1.11.0 build passed Unity checks (including notice validation) and installed as
an in-place update without clearing app data. Python and mocked Node tests cover the
display/action separation, checksum gate, countdown reset, missing display ack and
session change. A live guided run and visual/audio review are reported separately.

Live checkpoint (2026-09-27): `.oryn-inspection/guided-2SB7zs/report.json` passed
on the manifest-prepared drone (`3847f26e59ad61f6a7bcb4ab2b3c3baf90cf1a9e5757c23772b39373afb1e729`).
The correct model auto-started after readiness; explode/reassemble receipts executed,
all 39 geometric targets matched spread/restoration, and the Quest acknowledged the
terminal `passed` panel (sequence 8). No chat response was required. Display ack
confirms the runtime accepted/displayed the message; perceived readability and
audibility remain user-experience checks, not proven by that ack.

## Earlier inspection setup

Development tooling only. No Unity changes or SDK upgrades are required for this
inspection. Configuration: Unity 6000.6.3f1, Meta Core 205.0.0, OpenXR 1.18.0, the
SDK-bundled v205 MCP proxy, and ORYN 1.10.0 development APK on Quest 2 / Horizon OS 207.

## Run

Use Node.js 18+ and the installed bundled proxy at
`~/meta-xr-operator/meta-xr-operator-mcp-proxy`, or pass `--proxy /absolute/path`.
Keep ORYN open and the Quest awake, with the existing 39-part drone fixture loaded.
Avoid moving the assembly: this is sequential observation, not an atomic snapshot.
The runner never launches apps, sets device properties, forwards ports, wakes the
headset, or changes scene/input state automatically.

Each request is bounded to 15 seconds and a complete run to two minutes. Replies
are size-limited. Backend callbacks may time out earlier than these limits.

```sh
node Orchestrator/xr_inspection.cjs
node Orchestrator/xr_inspection.cjs --capture
node --test Orchestrator/test_xr_inspection.cjs
```

`--capture` explicitly requests a headset image. Approve the Quest consent dialog
if shown, then rerun; there are no automatic retries. Captures may contain private
room imagery, although passthrough appeared black during the initial v205 check.
Reports and captures go to private `.oryn-inspection/run-*` directories ignored by
Git. No provider keys are passed to the proxy and no generation/cognition API calls
are made. Meta's proxy has its own diagnostic logs and telemetry behavior outside
this script's output directory.

## Preconditions and reconnection

USB must be authorized and the development APK must include Operator. The current
connection uses host port 8720 forwarded to device port 8720 and the temporary
`debug.oculus.experimentalEnabled=1` device setting. Reboot/disconnection may require
setup again. Do not overwrite a Simulator's use of the same host port.

Codex's `oryn-xr-inspect` registration has an inspection-only tool allowlist. This
runner independently uses a stricter allowlist with the same bundled proxy, so it
also works before a Codex MCP configuration reload. No VR CLI, Simulator, or SDK
upgrade is performed. Newer documentation's hand-gesture capabilities should not
be assumed available in v205. Production ORYN does not depend on this runner.

## Results

- **PASS / exit 0:** expected app, focused session, workspace roots, exactly 39
  unique fixture part IDs, finite transforms and positive scales for the model and
  every part, and the same focused session at completion. With `--capture`, a PNG
  header with nonzero dimensions must also be returned and saved.
- **FAIL / exit 1:** observed structure or transforms violate those checks.
- **BLOCKED / exit 2:** unavailable app/proxy, sleeping headset, changed session,
  capture permission pending, timeout, or unreadable tool response. Not a pass.

v205 sometimes returns error text inside `isError:false`; the runner requires JSON
for state queries and rejects that text. Reports explicitly separate completed
checks from overall success and identify captures needing visual review.

This does NOT verify identities, real-world dimensions/reachability, visibility,
image quality, furniture collisions, gesture recognition, isolated-part behavior,
or performance. Inactive parts can be legitimate in an isolated assembly.
Screenshot capture is not a visual assertion: review the image separately.
The installed v205 pose lookup cannot resolve inactive GameObjects. The generic
full-transform inspection can therefore block on an isolated assembly. The
isolation regression below uses an explicit active-only observation mode, not
fabricated or cached transforms for hidden objects.

The read-only runner passed all eight checks on the connected Quest on
2026-09-27, including capture. The captured view only included an edge of the
drone, so that run did not validate the full visual presentation.

## Explode/reassemble regression (explicit actions)

This separate development runner uses read-only Operator observations plus ORYN's
existing validated USB command protocol. It does **not** enable Operator input or
transform writes, modify the Unity project, call paid providers, or require the
browser command service. Python uses the existing `CommandTransport`; both helper
processes receive a restricted environment without provider keys.

```sh
node Orchestrator/xr_assembly_test.cjs --execute
node --test Orchestrator/test_xr_inspection.cjs Orchestrator/test_xr_assembly.cjs
python3 -m unittest discover -s Orchestrator -p 'test_xr_command_bridge.py' -v
```

Requires Node 18+, Python 3 (default `/opt/homebrew/bin/python3`, override with
`--python /absolute/path`), the installed proxy (`--proxy /absolute/path`), and
the existing USB connection. The Operator forwarding entry on port 8720 must
point to the same authorized Quest as the command bridge. No forwarding, device
settings, app launching, or keep-awake changes are performed automatically.

Start with `Oryn 39-part model 1` **assembled and selected as a whole**, no isolation,
ORYN focused, and hands relaxed away from it. The runner refuses a part-selected,
exploded, stale, sleeping, or busy starting state instead of resetting user work.
`--execute` authorizes exactly one explode followed by one reassemble, subject to
preconditions. It records:

1. Baseline transforms and a stable, ready command context.
2. One explode execution receipt, then all 39 part transforms. Each position must
   equal `root + 2.1 * (baselinePosition - root)`; rotations and scales must remain
   unchanged. At least one part must move by more than the position tolerance.
3. One reassemble execution receipt, then all 39 parts back at baseline position,
   orientation, scale and active state. The root must stay unchanged throughout.

Tolerance: 3 mm Euclidean position error, 0.2 degrees quaternion orientation
error, and per-axis scale error of `0.00001 + 0.0001 * baselineScale`. The spread
factor matches `OrynAssembly.SetSpread(1)`; update this regression deliberately if
the runtime contract changes. These tolerances are test policy, not a claim about
physical headset tracking accuracy. Samples are sequential, not atomic.

Private, Git-ignored `.oryn-inspection/assembly-*/report.json` reports contain
before/after transforms, command IDs, receipts, tolerances and recovery status.
Command IDs are saved before dispatch. Reports omit labels, credentials and
images. Receipt polling is bounded to 12 reads; commands are never resent. ADB
calls have 5-second timeouts, Python invocations 25 seconds, Operator calls 15
seconds; a 150-second run budget prevents starting further operations after that
deadline (an in-flight bounded operation can finish later).

**PASS** requires receipts **and** matching observations. **FAIL** means observed
geometry does not satisfy the spread/restoration checks. **BLOCKED** means the
evidence is unavailable or unreliable (e.g. focus loss, root movement, changed
session/asset/records, stale context, missing receipt). No result is inferred from
file transfer alone. A geometry mismatch still permits the planned, validated
reassembly, but uncertain transport/context stops further actions. If stopped
after explosion, the drone may remain exploded; read the report and current scene
before manually reassembling. A timed-out command may still execute until its
30-second expiry. Do not automatically restart the test to resolve uncertainty.

This test does **not** validate pinch/prayer recognition, real grabbing, collision
feel, UI usability, semantic labels, or visual quality. Those need separate tests.
Live validation on 2026-09-27: **PASS** on Quest 2, ORYN 1.10.0. Initial preflights
stopped without dispatch because the headset state was stale or the grab/gesture
gate reported busy. Once ready, exactly one explode and one reassemble were
confirmed executed. All 39 parts matched the expected spread, and all 39 returned
to baseline. Maximum world-position errors were approximately 0.000000228 m for
spread and 0.000000126 m for restoration, well inside the 0.003 m tolerance;
orientation differences were zero and scales matched. The drone was left assembled.
Local evidence: `.oryn-inspection/assembly-nFmdjm/report.json` (intentionally not
committed). Offline verification: 30 Node tests and 92 Python tests passed.

## Select/isolate/reassemble regression

```sh
node Orchestrator/xr_assembly_test.cjs --execute --test isolation --part 4
```

The same initial conditions and safety gates apply. `--part` is a fixture part
number (1–39, default 1), **not** an inferred semantic label. The requested part
must already have a persisted knowledge record; otherwise the test stops before
selection. Part 4 has a record in the current development fixture. The adapter
reads only that record, validates the asset/part IDs and renderer-path hash, and
returns the geometry name without annotation text. The scene must contain that
exact unique geometry wrapper. It never assumes that part ordinal equals mesh
name or that a user label proves identity.

The cycle sends one `select`, one `isolate`, and one `reassemble`, each with fresh
context validation, explicit part ID where required, and an execution receipt.
It verifies selection without transform changes, all 39 active flags during
isolation, exactly the intended target active, stable root/target transforms,
and all 39 active states and transforms after restoration. A failed selection
geometry check skips isolation and proceeds to guarded restoration. Loss of
focus/context or uncertain execution stops without blind cleanup as before.

**Observation limitation:** v205 lists inactive objects in hierarchy results but
cannot read their transforms. The isolated-phase report explicitly records the
38 hidden transforms as `NOT_OBSERVED`; it does not reuse baseline transforms and
claim to have measured them. The hierarchy is sampled again to detect changes
while measuring the active target. Hidden parts are fully measured once restored.
Active flags establish scene activation, **not** pixel visibility, occlusion,
renderer/material correctness, or hand-interaction quality. No screenshots or
controller input are injected by this cycle.

Live validation on 2026-09-27: **PASS**, geometric part 4 (`island_004`), all three
commands confirmed executed. Exactly one of 39 parts remained active; restoration
matched all 39 baseline transforms. Evidence:
`.oryn-inspection/assembly-8nhCJ2/report.json`. An earlier attempt confirmed
isolation but blocked on the inactive-pose limitation; an explicitly guarded
reassembly restored all 39 parts and was recorded in
`.oryn-inspection/assembly-JqjZef/recovery.json` before rerunning the corrected test.

Reference: [Meta's Quest setup](https://developers.meta.com/horizon/documentation/unity/meta-xr-operator/quest/).
