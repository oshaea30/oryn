# Intent preservation 004 — measured result

**Explicit requirement accounting improved; complete request fulfillment remains
unproven.** All four cases produced complete plans with every extracted requirement
ID accounted for. The lamp's omitted spatial requirement now survives into a typed
containment binding. Unsupported requirements prevent construction. The geometry
executor was unchanged throughout.

[Protocol](REQUIREMENTS_EXPERIMENT.md) · [Retained evidence](results/requirements-004.json).
Initial code freeze `13d0d4c`; separately recorded local ID-validation correction
`a6f4357`. Existing gpt-6-sol, medium reasoning, unchanged 12,288 construction-output
limit. Four extraction calls and five planning calls; no paid completeness reviewer.

| Case | Coverage and execution | Measured service time |
|---|---|---:|
| Leaf/seed lamp | 12 IDs accounted for; inside bound to containment; suspension and glow explicitly unsupported; geometry prevented | 73.62 s to blocked result |
| Drone | 13 IDs bound; 19 parts; declared geometry checks pass on first attempt | 82.22 s to first render |
| Speaker | 12 IDs bound; 11 parts; disconnected driver solid repaired automatically under the frozen assembly contract; declared checks then pass | 94.84 s first render; 121.32 s through repair |
| Known sharpener | 9 IDs bound; 6 parts; two connection checks fail; repair not dispatched because reservation would exceed batch cap | 76.98 s through first render, excluding the revalidation pause |

Times sum that case's extraction and planning/build/render stages; they exclude
waiting behind other cases, replayed earlier role planning and client delivery.
The sharpener total includes its original extraction, not its near-zero replay.
No time to a complete, accepted object is established. Exact JBL remains evidence-blocked.

## What the gate actually proved

The lamp inventory explicitly contains seed existence, seed shape, curled-leaf
shape, seed-inside-leaf, suspension, emitted light and inspection. Its plan binds
inside to `containment:0`. The gate does not accept a parent link or a face mate as
substitute evidence for containment. It accounts for suspension and emission as
required unsupported results, so no lamp geometry executes. This is honest refusal
to claim completion, not a successful generated lamp. Containment geometry itself
was not tested because the pre-execution gate stopped the whole plan.

All live plans had complete ID coverage on their first attempt. Missing-binding
repair was therefore demonstrated in synthetic pipeline tests, not live output.
Those tests also prove that missing, unrelated, reversed or unsupported mandatory
bindings cannot reach the geometry builder. Optional unsupported remains visible;
evidence-required items cannot be justified with arbitrary geometry.

The speaker correction fixed two disconnected solids in its driver without
changing requirement IDs or locked assembly relationships. The sharpener's finite
drive-shaft surface interval intersects its flange, and axial engagement is about
3.55 mm where the plan declares a 6 mm minimum. These are downstream geometry
failures after coverage, not dropped IDs. It uses two coaxial and three face mates;
coaxial geometry is now exercised by live output, but that output fails validation.

## Interpretation and appearance still need work

Post-run source assessment is **partial**, separate from the complete ID accounting:

- Lamp: the critical quoted details survive. However, suspension is retained as an
  unexpressible `other` predicate, and the unsupported explanation demands verified
  physical hanging. The original request expressly allows a non-buildable concept.
  Visual suspension and engineering verification need distinct interpretations.
- Drone: quadcopter counts, inspection and separation survive. The inventory has no
  propulsion-axis relationship. Rendered geometry shows two propellers oriented
  horizontally and two vertically, despite declared numeric checks passing.
- Speaker: portable Bluetooth-speaker appearance, inspection and separation survive,
  and all proposed roles appear. But a broad appearance string plus named component
  placeholders does not establish that the main systems are faithfully represented.
- Sharpener: crank existence, hand-cranked appearance, inspection and separation
  survive. A labeled smooth cutter and general appearance requirement do not
  establish useful cutting geometry or mechanical coupling.

The non-lamp inventories declare no semantic relation predicates; their construction
plans independently choose mates. Many internal roles are design choices, not
mandatory requirements. That can be appropriate for an unspecified generic design,
but this test does not establish whether the resulting role set fully explains the
requested systems. Source quotations are traceability, not proof of interpretation.

The visual outputs remain crude research geometry. No visual-quality, unfamiliar-
object, physical-disassembly, animation or Quest acceptance is claimed. No manual
repair of an inventory, binding, position or mesh was performed.

## Output limits and local validation correction

003 speaker/sharpener used 10,438/9,528 reasoning tokens out of 12,288 and returned
incomplete responses. In 004 the initial speaker plan completed at 7,702 output
(4,436 reasoning), and sharpener at 5,569 (3,624 reasoning). Drone used 7,428
(2,041 reasoning); lamp 4,990 (3,624 reasoning); speaker repair 3,330 (299 reasoning).
Every paid response completed. Extraction took roughly 9–13 seconds per case.
Changed reasoning effort, staging and compact serialization prevent assigning the
improvement to one cause. Shape sharing is request-authored, not a curated object
library; an offline audit reproduced previous geometry exactly without supplying
those old outputs to the model. New binding overhead is excluded from that byte audit.

The sharpener's original extraction used uppercase IDs. The prompt/schema permitted
that, but the local validator initially rejected it. The correction accepts stable
ASCII upper/lowercase IDs without normalizing them. The exact saved response was
revalidated and its previously unattempted planning call continued. Original error,
response hash and both run records remain preserved. This was no paid extraction
retry or semantic/output repair, and not an uninterrupted frozen-run success.

## Cost, verification and next decision

Calculated API cost **$0.3953575**, with zero new uncertain reservations; provider
invoice cost remains unknown. The $0.50 batch, $2 UTC daily and $5 aggregate ceilings
were unchanged. The remaining $0.1046425 could not reserve the sharpener repair's
maximum quoted cost. Its admission failed before generation dispatch; no repair
quality conclusion can be drawn. Prior uncertain charges remain reserved.

76 targeted test executions pass, including spend/duplicate/uncertain-outcome guards,
pre-build coverage, immutable requirements and geometry regression. Browser checks
cover selection, separation, reset and immutable stored geometry for all four built
outputs. Executor hashes match the initial freeze. Raw responses/meshes stay in local
`Builds/NativeObjects/requirements-run-004` and its `-revalidation` companion.

Keep the geometry executor frozen. The next bounded work should clarify the meaning
and fidelity of extracted requirements: visible conceptual properties, explicitly
requested behavior, implied structural relationships and verified physical function.
Test that distinction on varied request wording before paying for more geometry.
Do not treat an appearance binding as a completed visual or functional requirement.
The deterministic gate is useful infrastructure; this batch does not prove lossless
natural-language understanding or a working general object generator.
