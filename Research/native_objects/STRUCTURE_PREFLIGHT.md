# Construction-guided generation: preflight 001

2026-09-30. Question: can an application-produced construction plan yield a useful
assembly quickly, then improve its appearance while preserving its components?
This adds latency and identity measurements to the existing quality gate. It does
not replace that gate, establish model superiority, or authorize a format project.

## Result: no paid dispatch from this preflight

Four approaches were checked. None has yet established the complete input path
needed for the unchanged ORYN cases. This is a bounded capability audit, not a
claim that no available model could work. No geometry inference, new model API
calls, GPU rental, product edits or output repairs were performed.

- **MegaParts / MeshCoder 1.5:** promising structural control, but the inspected
  repository says its code will be released. The available MeshCoder path takes
  point clouds and emits Blender code; it is not the announced text/layout model.
  Do not substitute one for the other. [Pinned README](https://github.com/InternRobotics/MeshCoder/blob/2f7b3e45ee515caf6bb152a2fad06a1298612496/README.md).
- **PAct:** released, but documents eight fixed semantic labels and at most eight
  parts after merging. This does not cover the unchanged speaker's nine roles.
  Its approximately 15-second claim also excludes potentially expensive textured
  mesh export. No timing claim is adopted for ORYN. [Pinned README](https://github.com/Mobiuslqm/PAct/blob/a5ccec5056e7b27f39ddb5b83613c0efba9b2861/README.md).
- **OmniPart:** the released entrypoint uses an image and segmentation mask,
  generates occupied coordinates, predicts boxes, then jointly synthesizes parts.
  Its lower-level synthesis input accepts boxes and reuses the occupied coordinates;
  that is worth investigating, but does not establish acceptance of arbitrary
  ORYN layouts or hidden internals. [Pinned entrypoint](https://github.com/HKU-MMLab/OmniPart/blob/ceb1a4ff2d279a57a673d0f65954735c6bf8231c/scripts/inference_omnipart.py).
- **Procedura:** its project describes assembly-guided procedural generation, but
  both Paper and Code links resolved back to the project page during this audit.
  A reproducible release was not established; do not treat showcase claims as a
  runnable dependency. [Project page](https://spatiaos.github.io/projects/procedura/).

OmniPart's input utilities downsample masks to 37×37, reorder surviving labels by
vertical position, and skip boxes containing no occupied coordinates. Consequently,
an adapter must retain the original-to-model identity mapping and detect dropped
roles. A single visible-surface mask cannot itself identify a fully occluded part.
These are input-path findings, not proof that the model cannot infer internals.
[Reviewed utilities](https://github.com/HKU-MMLab/OmniPart/blob/ceb1a4ff2d279a57a673d0f65954735c6bf8231c/modules/inference_utils.py).

The [CPU reproduction](results/structure-preflight-001-mask.json) executes the exact
hash-checked upstream NumPy downsampling function. Nine large synthetic regions
survive; replacing the ninth with one visible pixel inside another region's bin
loses label 9. It does not execute the model, test full preprocessing, or estimate
real-object failure rates. No mask was painted for an actual benchmark object.

Pinned source URLs and checksums are in [the source record](results/structure-preflight-001-sources.json).
To reproduce, download the pinned utility file above unchanged, then run:

```sh
python3 -m Research.native_objects.check_omnipart_mask \
  --source /path/to/inference_utils.py --output /tmp/new-mask-check.json
```

## The missing capability to test next

The existing application-owned planner proposes component **groups**, not a
construction plan: dimensions, instance counts, placement and connections remain
unspecified. CubePart already used a shared whole-object encoding. Merely adding
another shared representation or preserving filenames does not solve that gap.

The next implementation boundary is an isolated application-owned construction
proposal using the existing research representation: preserve the request and
all role groups, distinguish repeated instances, propose placement and relationships,
and mark design choices as unverified. It must have a realizable geometry path.
A plan-only result is not a generated object; do not build another planning layer
unless the receiving geometry method's inputs are concrete.

For OmniPart specifically, the unresolved bridge is automatic creation of a
consistent reference, part masks, occupied coordinates and layout with no dropped
planned roles. Hand-authoring these for the drone would defeat the experiment.
Establish that bridge offline before selecting it for a paid run. If it requires
another full object generation or cannot express hidden roles, report that cost
or incompatibility rather than removing requirements. Procedural realization is
an alternative hypothesis, not an implemented fallback in this checkpoint.

## Predeclared acceptance and measurement rules

These rules are fixed now; a provider-specific execution protocol (pinned weights,
inputs, hardware, parameters, timeout, cleanup and exact cost ceiling) is still
required before paid execution. There is no runnable GPU protocol yet.

1. Preserve all four [original requests](planning_cases_001.json): drone, nine-role
   speaker, creative leaf/seed lamp, and evidence-blocked exact JBL. Do not merge
   roles to fit an engine. Exact JBL must remain blocked without matching evidence.
2. Use one application policy, no object-specific recipes, manual masks, repairs,
   relabeling, tuned prompts or seed search. Retain failures and unsupported cases.
   Existing plans may be replayed for an isolated geometry test, but report their
   prior planning time separately; replay timing is not fresh-request latency.
3. Reuse the existing package/viewer. A coarse object must already satisfy all five
   [Cube scorecard dimensions](CUBE_COMPARISON.md#predeclared-scorecard): concept,
   coherence, role coverage, independent selection, and plausible assembly. Require
   2/2 on each. Boxes, labels and the existence of files do not pass. A genuine
   block-shaped component can pass on its merits; placeholder geometry cannot.
4. Keep component identity, group membership, parent references, units and assembly
   frame across refinement. Bind a selection before refinement and verify that it
   still selects the same component afterward; explode/reset must retain it too.
   Compare geometry and placement visually as well as IDs. ID equality alone cannot
   detect a motor turning into a propeller. Any intentional layout revision starts
   a new proposal and does not count as identity-preserving refinement.
5. Record monotonic times for request, plan, input preparation, model load, first
   renderable geometry, first interactable checkpoint and final refinement.
   Preserve every checkpoint so the earliest one meeting the quality gate can be
   identified afterward. Count transfer, export and validation; synchronize GPU
   timing. Record cold and resident-model runs separately, including compilation
   and cache state. Never infer warm totals by subtracting guessed loading times.
6. Research UX targets: first useful, selectable assembly within **30 seconds**;
   refined assembly within **120 seconds** of a fresh request with resident models.
   These are proposed product targets, not measured capabilities or industry norms.
   Also report actual cold-start time. A spinner or unusable preview stops no clock.
7. Report cost to first useful output and final output, plus rental/setup/storage
   cost. Identify repeated full-object synthesis and encoding from actual stage
   traces; do not label all sequential stages duplicated work. Stay within the
   existing aggregate $5 research ceiling after prior spend; no budget reset.

**Decision:** all three generic/creative cases must pass quality, identity and the
warm latency targets, with exact-product restraint preserved, to justify a small
predeclared unseen-case/repeatability trial. That would still not prove generality.
Quality passes with excessive latency indicate an offline-creation candidate;
quality/identity failures stop the configuration. Setup failure or missing release
is inconclusive model-quality evidence. Improvements over Cube are descriptive;
a matched with/without-guidance comparison is needed for causal claims about planning.
Quest performance remains a later gate. Retrieval infrastructure, Jev, answering,
motion inference, training and new object formats remain deferred.
