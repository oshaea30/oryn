# Solid construction 002 — measured result

**Automatic geometric correction demonstrated on two examples; finished-object
quality remains unproven.** Frozen execution code: `d51af37`.
[Protocol](SOLID_EXPERIMENT.md) · [Recorded results](results/solid-002.json).
No manual output repairs, transport retries, GPU rental or Quest promotion.

ORYN called OpenAI `gpt-6-sol` with high reasoning for construction and medium for
separate-context visual review. Astra was not tested. General boolean operations,
rounded corners and repetition extended the same procedural builder. These results
combine those changes with higher reasoning and feedback; they do not isolate any
one change's effect. The model chose all object-specific geometry and corrections.

| Case | Outcome | Render ready | Final numeric checks | Model visual review |
|---|---|---:|---|---|
| Drone | No response retained | unavailable | unassessed | unassessed |
| Speaker | No response retained | unavailable | unassessed | unassessed |
| Leaf/seed lamp | Two completed attempts | 92.21 / 160.49 s | pass after revision | revise, 8/10 |
| Pencil sharpener | Two completed attempts | 104.02 / 227.00 s | pass after revision | revise, 7/10 |

Render times accumulate from each case's start, including the first review before
a second construction. Final review adds 14.70 seconds for the lamp and 20.04 for
the sharpener. Prior role plans were replayed. No product-usefulness or end-to-end
Quest latency pass was established. Hosted cold/warm status remains unknown.
The sharpener was a known failure case by this experiment, not a fresh held-out case.
Exact-product reconstruction stayed evidence-blocked without a geometry call.

## Evidence and limits

The negative-control review rejected the unchanged old sharpener and identified
its blocked pencil path and missing drive connection. That supports using the
reviewer experimentally, not treating its opinion as independent certification.

For the lamp, the first containment check failed. ORYN received its own visual
critique plus the failed measurement and moved the seed inside the shade's convex
envelope while maintaining clearance. The second proposal passes all declared
checks. The review still cannot clearly see its suspension in the assembled views.
The anchor check does pass, so this is not proof of a missing geometric connection.
The output is a faceted leaf-like shade and warm-colored seed. The renderer has no
emissive material or lighting support; absent glow cannot be solved by coordinate
changes alone. That is a capability limit, not a reason to buy repeated revisions.

The sharpener now has actual housing/guide openings and a drawer aperture. Its
first drawer consisted of two solid islands; application feedback prompted a
connected revision. The final declared checks pass. Independent inspection of the
recorded images still does not establish a convincing feed-to-cutting-edge and
crank-to-cutter relationship. The nominal helical cutter appears as a ribbed cylinder.
Reviewer scores are not substituted for this uncertainty. No engineering claim.

Drone and speaker requests each ended after approximately 120 seconds without a
retained response. The sender's timeout is 120 seconds, but the frozen runner did
not preserve the exception category. Timeout is a likely explanation, not confirmed
from the saved exception. These are delivery failures, not geometry-quality results.
The reservations remain held. Neither request was resubmitted.

The contact sheets provide overview and isolated-part views. Small or occluded
interfaces may be hard to assess; visual review should not turn uncertainty into
an invented disconnection. More useful interface views and safe transport diagnostics
are needed before a further bounded experiment, not manual fixes to these outputs.

## Cost, checks and decision

Calculated completed-request cost: **$0.4414925**. Uncertain reservations: **$0.25535**.
Total charged/held against the experiment: **$0.6968425**, below its $1.35 cap.
Provider invoiced cost remains unknown. No additional live calls followed the batch.
All original proposals, review journals, inspections and geometric reports are
retained with hashes. Raw responses and exported packages remain in the local
`Builds/NativeObjects/solid-run-002` folder.

Eighteen solid geometry/review/spending tests pass, including safe failure reporting
added after the frozen run. Four browser outputs load, select, separate and reset;
selection and separation survive each revision switch, with unsupported motion
disabled. Local browser verification is not Quest performance acceptance.

Stop this frozen batch at its predeclared bounds. Preserve the general construction
and automatic correction capability, but do not promote either output as a complete
working object. The broader goal remains open. Diagnose response delivery and
improve interface observability before further paid comparisons. A fresh unfamiliar
case is still required if a future candidate passes; no training, provider sweep,
new object format, answering or motion expansion is justified by this result.
