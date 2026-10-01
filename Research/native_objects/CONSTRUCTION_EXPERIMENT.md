# Procedural construction experiment 001 — frozen before model execution

Question: can ORYN itself choose geometry and spatial relationships that realize
its component proposals, with one policy across different requests?

This is an isolated structural-control experiment. It is not a final rendering
architecture or a new object format. The existing research package and inspector
carry the generated geometry. Production and Quest are unchanged.

## Inputs, method and limits

Replay the three generic/creative requests and role groups from planning-001:
drone, nine-role speaker, leaf/seed lamp. Preserve the exact JBL evidence block.
After freezing code/policy, choose one new request and obtain its role groups using
the existing application planner, then run the same construction policy once.
The unfamiliar case is withheld from implementation, not necessarily from model
training. One example only tests limited transfer.

The model supplies all instance counts, dimensions, transforms, parent references,
mount anchors, containment, clearances and proposed mirror relationships. No object
recipes or numerical examples enter its prompt. Six general geometry operations:
box, ellipsoid, cylinder, open tube, open box shell and curved/tapered loft. At most
32 instances, six forms each. The interpreter never executes arbitrary model code.
Unsupported shape requests and malformed proposals remain failures; no added
primitive, prompt correction, per-output geometry repair, relabeling or paid retry.

A single gpt-6-sol medium call per construction case, at most 8,192 output tokens
and $0.12 per call; four cases at most $0.48. One held-out role-planning call at most
$0.05 brings this experiment ceiling to $0.53. Shared $2/day cognition ledger,
reviewed rate expiry and uncertain-reservation accounting still apply. These are
construction research operations, not per-object knowledge investigations; existing
production profile and investigation caps remain unchanged. Prior research spend
also counts toward the existing aggregate $5 ceiling. No GPU rental or retrieval.
Freeze each exact request body/schema/instructions and source-plan checksum in the
run record. Fixed experiment/case operation IDs prevent resending across output
folders or changed prompts. Journal before sending, preserve raw model outputs.

## Measurements and predeclared assessment

- Contract: finite bounded operations, unchanged role coverage, individual repeated
  instances, one acyclic assembly tree with explicit parent connections.
- Mounts: world anchor mismatch <=1 mm, each anchor <=1 mm from actual generated
  triangles. This is an attachment check, not surface-area/normal/load validation.
- Containment: every contained mesh vertex inside the generated convex shell cavity
  inset by declared clearance. For tubes, test actual polygonal cavity half-planes.
- Clearance: world AABB separation is a conservative distance lower bound. Overlapping
  bounds cannot certify a positive requested gap. Zero minimum proves no separation.
- Symmetry: declared reflected world bounds agree within 1 mm. Not full mesh symmetry.
- Coverage: review whether the proposal omitted an essential relationship to evade
  checking. Numeric checks alone cannot establish semantic completeness or engineering
  validity. General collision, manufacturability, electronics and mechanics unassessed.

Structural control passes a case only if the contract and all declared relationship
checks pass AND qualitative review finds meaningful role geometry, appropriate
connections and no essential omitted constraints. Retain partial/fail observations.
Visual usefulness uses the existing five-dimension 0/1/2 Cube scorecard independently;
all five need 2 for the product visual gate. Crude but consistent geometry can supply
structural evidence without passing visual quality. No goalpost changes after output.

Record model-request wall time (including token count), local build/check/export time
and file-ready time. Browser readiness/quality must be checked separately; file-ready
is not time-to-useful. Existing input planning was replayed, so these are not fresh
request totals. Hosted model cold/warm state is unknown. No inferred warm timings.
The 30-second useful / 120-second refined targets remain product targets, reported
separately from structural viability. A 42-second structurally sound result is useful
research evidence and a latency miss, not automatically discarded.

Build each unchanged proposal at 12 and 24 angular segments. Verify component IDs,
roles, parents, assembly frame and selection across those checkpoints. This tests
our deterministic tessellation and binding, **not** a generative polishing model.
No polished-refinement latency will be claimed; that stage is not implemented.

## Decision and reproduction

No manual corrections. Preserve all three outputs and run the predeclared unfamiliar
case after freeze, even if early cases fail, to characterize coverage without tuning.
If structural control works but appearance fails, record that split before considering
a constrained appearance experiment. If structure fails, identify the failure class;
do not fix the generated coordinates by hand. No automatic seeds or provider sweep.

```sh
python3 -m unittest Research.native_objects.test_construction Research.native_objects.test_construction_runner -v
python3 -m Research.native_objects.construction_experiment --output Builds/NativeObjects/new-construction-preview
# Explicit execution uses the saved research connection and existing usage ledger:
python3 -m Research.native_objects.construction_experiment --output Builds/NativeObjects/new-construction-run --execute
```

The protocol and implementation commit preceding execution is recorded in the result.
