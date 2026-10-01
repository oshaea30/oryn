# Repair 012–013 — one successful local repair, coupled orientation still fails

**Bounded repair works on the saved fan, but this is not a reliable general generator.**
The fan's one model-authored patch passes all 55 existing geometry checks and preserves
all 55 previously passing facts. The new drone plan completes, but its one patch leaves
one motor/propeller pair upside down and breaks two symmetry checks. The speaker returns
valid typed requirements and correctly stops on an unsupported front-face relationship.
No output was manually repaired, sent to Quest, or promoted into the product.

012 was frozen at `4d4c72f`; the separately frozen compact-input continuation 013 was
committed at `e0aaa91`. Both use gpt-6-sol medium, unchanged initial output allowances,
geometry executor, primitives, numeric tolerances, source requests and role catalogs.
Supplied catalogs remain an experimental limitation: autonomous discovery is unproven.

## What the application now does

- Creates a bounded background request once, journals its response ID, polls that same
  response, and settles verified usage once. Interruption, cancellation, stale input,
  unknown creation and malformed billing paths have local tests. All four live requests
  completed without retrieval interruption or cancellation. Live interruption recovery
  is therefore unexercised; the former synchronous timeout remains unknown and held.
- Computes an edit scope from failed checks and all users of affected shared shapes.
  A patch may replace existing permitted shapes or feature selectors. It cannot rewrite
  components, requirements, bindings, mates, groups or tolerances. Unrelated local
  geometry remains byte-equivalent in the expanded plan. Dependent poses can still move.
- Rebuilds and validates the entire assembly after a patch, including all-pair static
  interference, real feature geometry, global groups and preserved measurements.
  This is local model editing, not incremental geometry execution.
- Uses typed short keys for the speaker extraction, retaining output schema enums.
  The invalid `animate` exclusion from 011 is no longer emitted; `motion` is valid.
- Compacts repeated repair facts on input without deleting any. The blocked drone
  request had 24,456 tokens. Thirteen tables retain every one of its 275 passing facts;
  exact decode equality plus compact JSON reduces the request to 15,987 tokens. The
  16,000 input limit and patch output schema remain unchanged.

## Results

| Case | What happened | Actual conclusion |
|---|---|---|
| Three-fan row | Reuses the untouched 010 starting plan. Two shared shapes and six feature selectors change; seven parts remain. Twelve failed checks become zero, with zero preserved-fact regressions. The panel is unchanged. | First successful bounded model repair in this comparison. The row is recognizable and consistent, but simplified: center supports/bearings and engineering completeness are not established. A partial visual result, not a polished finished-object pass. |
| Generic drone | New 19-part plan covers its 34 requirements. 259/261 measured checks pass; two motor/propeller pairs point sideways. Its one local patch corrects one pair and inverts the other; four checks then fail, including two new symmetry regressions. Eleven unrelated parts remain unchanged. | Failed candidate, correctly rejected. No generalized repair success. A high percentage of passing checks cannot offset an invalid assembly. |
| Two-driver speaker | Valid 16-record inventory preserves side-by-side placement, forward orientation, inspection/explosion, and waived audio/motion. Required `r9`, “in enclosure front face,” has no executable spatial binding. | No geometry. This trial fixes the format failure; it does not resolve the separate placement representation. Do not silently convert the phrase into the narrower existing exterior-contact rule. |

The fan patch changes five blades to four, a permissible design choice in the unchanged
request, to satisfy symmetry. This is explicitly model-authored geometry, not a curated
replacement or hidden per-output edit. Its scope includes all three frames and all three
rotors because the shapes are shared. The complete initial plan is still retained.

The drone patch adds two mounting blocks to its shared motor shape and changes six
feature selectors. It remains within the permitted scope, but the negative-z pair's
axis becomes -Y instead of +Y. The motor and propeller mirror errors are 6 mm and 25 mm.
The original failed orientation requirements are `r15` and `r17`; the preservation gate
also names both symmetry regressions. The repaired drone is not admitted as a success.

## Latency diagnosis

| Live operation | Request wall time | Input tokens | Output tokens (reasoning included) | Geometry + full checks | Conservative cost |
|---|---:|---:|---:|---:|---:|
| Fan local patch | 62.08 s | 13,371 | 3,499 (2,887 reasoning) | 0.122 s | $0.0684175 |
| Speaker requirements | 24.85 s | 3,912 | 1,298 (516 reasoning) | Blocked; validation 0.0018 s | $0.0227600 |
| Drone initial plan | 98.68 s | 7,072 | 7,913 (3,397 reasoning) | 0.146 s | $0.0968100 |
| Drone local patch | 55.46 s | 15,987 | 3,400 (2,907 reasoning) | 0.166 s | $0.0739675 |
| **Total** | **241.07 s across four requests** | | | | **$0.2619550** |

Request time includes queue/network/polling, not a measured model-inference duration.
Geometry plus validation are combined because the existing executor performs both;
rendering/export raises local stage time to roughly 1.2–1.3 s. The old four-minute
synchronous failure still cannot be attributed more finely without its missing ID.
The new drone call completing does not prove that background mode makes planning faster.

The earlier unsuccessful whole-plan fan repair took 40.08 s and returned 3,601 output
tokens, including 1,439 reasoning tokens. The new patch returns 612 non-reasoning tokens
versus the old 2,162, but total output is similar and the new request takes longer.
There is evidence for better bounded repair, **not a demonstrated latency or cost win**.
This is one run, with changed feedback and request transport; causality is not isolated.

012 stopped before the drone patch because its input count exceeded the cap; no repair
reservation or creation occurred. 013 performs only that previously undispatched patch,
using the same baseline and scope. It adds no new starting plan, second repair cycle,
model switch or relaxed budget. Both frozen protocols and the failed input are retained.

## Decision from the comparison

Keep bounded edits, strict typed output, durable request tracking and full regression
checks. Do not spend another round asking the model to correct these same rotations.
The result supports revisiting how construction is solved before adding geometry features.

The current executor propagates fixed feature frames and fixed mate twists. Global
assembly orientation is checked afterward; it is not part of solving the poses. That
allows each local mate to pass while the declared shared-up direction fails. Under
repair, those twists are locked, so the model tries to compensate by changing mount
geometry. The added drone mounting blocks illustrate that limitation; they do not prove
this is the only possible correction.

The next bounded engineering question is whether existing declared assembly axes can
participate directly in pose solving, distinguishing required relationships from a
planner's provisional numeric pose choices. First test that locally on unrelated,
renamed arrangements and contradictory constraints, with retained old outputs unchanged.
A solver must explicitly reject conflicts rather than weaken requirements or fabricate
geometry. No additional primitive library or stronger model is justified by this result.
Keep the speaker's surface/embedding meaning as a separate unsupported capability test.

Visual quality remains a separate gate. Even a corrected drone here would be a crude
structural model, not the convincing generated object requested for ORYN. The native
milestone remains open; no brand/rendering treatment, animation or answers can substitute
for meaningful geometry. There is no new product route, GPU work or format project.

## Validation, budget and evidence

149 targeted local tests pass across the implemented recovery, immutable repair scope,
lossless transport, requirements, geometry and spending boundaries. Thirty-six browser
checks pass across four retained candidates: correct URL selection, component selection,
explode/isolate/reset, truthful status, group/preservation display and disabled motion.
No browser page errors. Desktop interaction is verified; Quest performance is unassessed.

All four new API calls have reconciled usage. No new uncertain holds, funding errors or
GPU charges. The $0.261955 conservative estimate stays inside the promised $0.78 combined
comparison allowance. Old uncertain reservations remain held. Shared local daily
allowance after these runs is $2.731665; this is not the provider balance or an invoice.
For subsequent budgeting, use at least $4.47 as the conservative prior research allowance
under the existing $5 aggregate ceiling. No additional paid run is dispatched here.

- [Fan before/after and initial drone](http://127.0.0.1:8775/repair-run-012/?case=cooling-fan-row-plan-1)
- [Failed drone repair](http://127.0.0.1:8775/repair-run-013/?case=generic-drone-plan-1)
- [012 protocol](LOCAL_REPAIR_EXPERIMENT.md) and [013 continuation](COMPACT_REPAIR_FOLLOWUP.md)
- [012 recorded result](results/repair-012.json) and [013 recorded result](results/repair-013.json)
- [012 audit](results/repair-012/post-run-audit.json) and [013 audit](results/repair-013/post-run-audit.json)
