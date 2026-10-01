# Assembly 011 — complete drone intent, stopped construction, unproven repair

**The drone produced a complete interpreted inventory; no new object completed.**
The construction request timed out at its four-minute deadline, and the batch stopped.
The speaker returned an invalid exclusion category and no front-surface translation.
The intended alternative fan repair was never dispatched. Cross-family generation and
repair improvement remain unproven; these are not successful geometry results.

The live run was frozen at `9bb9bbc`. Model gpt-6-sol medium, geometry executor,
primitive library, numeric tolerances, requests/catalogs and API output allowances
remain unchanged. The meaning layer's record capacity increased from 32 to the
underlying contract's 48; row transport shortened the response. This was disclosed
before dispatch. No generated answer, requirement, pose or mesh was manually repaired.

## Outcomes and separate blockers

| Case | Observed result | Boundary |
|---|---|---|
| Generic drone | 34 interpreted requirements, four declared groups, tested counts/radial layout/shared motor and propeller axes plus inspect/explode preserved. 2,156 output tokens, including 1,034 reasoning tokens, within the same 3,072 allowance. | Construction request timed out after 240.38 s without a saved response. No plan or geometry to judge. |
| Two-driver speaker | Complete 16-record response retained. `x1` uses exclusion domain `animate` where the registry requires `motion`; validation rejects it. `r7` still says “in enclosure front face,” but `spatial` is empty. | Contract invalid; no geometry. Surface-contact translation also remains unproven. Fixing the category alone would not resolve that missing translation. |
| Fan bank | Source extraction and initial solved geometry were verified unchanged before dispatch. The live batch stopped before replay execution or alternative repair. | No new fan repair result. Later free diagnostics replay only the two old 010 outputs. |

The drone also preserves a design-choice group for electronic speed controllers with
unsupported placement/orientation. That optional result is not silently converted to
required or counted as a realized assembly. The hidden conventional-layout assertions
pass, but supplied role catalogs and source coverage do not prove complete autonomous
understanding. One successful extraction is not a consistency estimate. Both transport
and record capacity changed, so rows alone are not established as the cause of success.

The timed-out provider call returned no response ID or usable output locally. Its
backend outcome/billing remains unknown. The record cannot establish whether the model
was reasoning slowly, the service stalled, or a response failed to reach the client.
No automatic retry, timeout extension, provider switch or reservation release occurred.

## Implemented and locally verified

- `on_surface` measures direct contact against a signed exterior planar side in the
  object frame. Real opposing faces, contact separation and actual solid extent are
  checked. Tests cover all six directions, root rotation, reversed mates, wrong side,
  gaps, buried/inset features and missing subjects. No live speaker realization passed.
- Repair feedback lists previously passing measured predicates while leaving positions
  and dimensions free. A locally retained, hash-locked baseline catches failed or
  missing facts afterward. Per-member placement/orientation truth is distinct from
  the validity of its supporting geometry. Existing constraint/binding locks remain.
- Free replay of 010's two fan plans preserves their exact compiled geometry. The first
  has zero regressions against itself. The old repair has **12 regressions**: three
  disconnected frames, three lost mate-overlap checks, and six reversed group axes.
  Detecting a known bad repair does not establish that new feedback improves repairs.

The old fan remains a recognizable, simplified row of fan-like parts with detached
mounting geometry and an inadequate center-support representation. Replayed assembled,
reverse, above, exploded and isolated-part views retain that failure. No polished-object,
mechanical, motion, Quest-performance or product pass.

[Old fan diagnostic replay](http://127.0.0.1:8775/assembly-run-011/diagnostic-replay/?case=cooling-fan-row-plan-1)
shows the new checks over unchanged old geometry, explicitly separate from the stopped
live experiment. Eighteen browser checks pass across both replayed candidates: correct
selection, separation, isolation, reset, failure labels, arrangement/regression display
and disabled motion. Zero browser page errors.

## Compact-format correction prepared after the batch

Positional rows preserved every field but removed the provider schema's per-field enum
constraints. The speaker's invalid category exposed that reliability cost. The application
correctly rejected it; it was not normalized into a fabricated passing response.

`typed_requirements.py` now provides an alternate lossless short-key representation
that retains every original field's schema constraint, including capability variants,
source/entity enums and exclusion domains. Offline schema-equivalence and round-trip
tests pass. Named JSON shrinks from 3,041 to 2,335 characters for the saved fan inventory,
and 3,336 to 2,534 for the saved speaker inventory (23–24%). These are character counts,
not output-token or latency measurements. A concrete request preview is saved locally;
**this alternative has not been dispatched or substituted into the recorded 011 run**.
It does not solve the separate surface-translation issue by itself.

## Cost and validation

| Operation | Usage estimate / reservation | Time |
|---|---:|---:|
| Drone interpretation | $0.0298725 settled estimate | 28.28 s |
| Speaker interpretation | $0.0211000 settled estimate | 17.32 s |
| Drone construction, unknown outcome | $0.1405625 held maximum reservation | 240.38 s until timeout |
| Total budget consumed or held | **$0.1915350** | 286.65 s live batch |

Completed calls total $0.0509725. These figures are calculated estimates/reservations,
not invoices or provider balance. No GPU cost or provider-funding error occurred.
The $0.95 batch cap, $6 shared daily cap and $5 aggregate cap were respected. Shared
local daily allowance after the run: $2.99362. Existing uncertain holds were retained;
this timeout adds one new hold. Use a conservative $4.20 prior research allowance for
a future explicitly bounded experiment, not a fresh $5 budget.

166 relevant local tests pass, including inherited spending checks, geometry/requirements
compatibility, lossless transport, real geometry surface checks, replay integrity,
missing/regressed facts and the post-batch typed-schema equivalence checks. Eighteen
browser checks pass on old diagnostic geometry. Neither count is a live generation pass.

## Next decision

Keep the measured arrangement/repair safeguards and unchanged geometry executor.
Before another paid comparison, use the prepared typed compact transport and resolve
how an uncertain long construction request can be observed without blindly resubmitting
it. The held reservation stays accounted for. Test mapping general surface relationships
separately; do not silently equate “in a front face” with a narrower contact relation.
The fan feedback comparison is still pending and should start from the same verified
initial plan, not from its failed repair. No new families, object recipes, larger token
caps, animation or product promotion are justified by this batch.

[Protocol](ASSEMBLY_FOLLOWUP.md) · [Recorded live results](results/assembly-011.json) ·
[Outcome audit](results/assembly-011/post-run-audit.json).
