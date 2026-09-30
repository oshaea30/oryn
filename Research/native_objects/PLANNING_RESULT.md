# Object planning experiment 001: result

**Pass for these four planning examples. The native-object generation goal remains unpassed.**

Protocol and shared instructions were frozen in commit `0224e76` before any live
call. The application made four model calls, using the same policy and no
case-specific recipes, supplied sources, external retrieval, retries or generated
geometry. Review criteria were not sent to the model. Results are retained in the
[measured record](results/planning-001.json); the [protocol](PLANNING_EXPERIMENT.md)
and [frozen criteria](planning_cases_001.json) define this result's scope.

| Request | Observed behavior | Frozen criteria |
| --- | --- | --- |
| Generic quadcopter | Seven proposed component roles; motors and propellers separate; layout choices labeled assumptions | Pass |
| Generic portable speaker | Nine proposed roles; driver/radiator choices labeled assumptions; acoustics and internal fit unknown | Pass |
| JBL Flip 7 internal assembly | Empty component list; asks for matching technical documents and revision instead of inventing a battery mount | Pass |
| Creative leaf/seed lamp | Five proposed roles preserve the creative request; no unnecessary demand for a real-product manual | Pass |

This is Codex's qualitative review against the predeclared criteria, not independent
human verification. Automated checks established output-contract compliance only.

## What actually ran

`OpenAIObjectPlanner` in the ORYN application code constructed each bounded
request, counted input, reserved budget, called the saved model connection,
validated the response and recorded usage. Codex launched and assessed the
experiment; it did not supply the returned component lists at runtime.

The model was `gpt-6-sol` with medium reasoning and a 2,048-token output cap.
Total conservative token-based estimate: **$0.020945** against a $0.20 ceiling.
Provider invoice amounts remain unknown. Per-case elapsed time, including counting
and local accounting, was 8.935 s, 11.381 s, 5.306 s and 7.869 s respectively.
Fifty offline planner/provider/spending tests passed before the live run.

## Boundaries and next decision

This is a small positive planning result, not evidence that ORYN can generate
arbitrary objects. All four requests concerned inspection; one response per case
does not establish repeatability, broad generalization or different detail levels.
No supplied evidence was assessed, no retrieval was executed, and source support
was not verified. The model's fidelity classification itself still needs semantic
review; category-specific guards cannot catch every misclassification.

The lists describe roles and groups, not meshes or a complete assembly. For example,
"four motors" still needs four realized instances, sensible placement and bindings
before independent selection is possible. Geometry generation, structural coherence,
component boundaries, fit and Quest performance remain untested here.

Retain this common planning policy unchanged for now. Next, evaluate whether a
candidate geometry pipeline can accept and realize these kinds of component plans,
using more than the drone as its test case. Freeze that test and its spending cap
before any GPU run. Keep a separate unseen-object/repeated planning evaluation
before claiming generality. No production route, new object format, automatic
retrieval system, Jev integration or additional PartCrafter runs are authorized by
this result.
