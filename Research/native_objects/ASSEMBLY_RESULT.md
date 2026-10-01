# Assembly 010 — measured result

**Group decisions and their checks are implemented. Cross-family generation has not
passed.** The fan and speaker preserve the tested arrangement intent. The fan reaches
geometry, where its attempted repair reverses the requested direction and is rejected.
The drone produces an incomplete inventory, so its arrangement inference is unassessed.

The same gpt-6-sol medium policy, compact construction schema and geometry executor
were used. No meshes, poses, requirement sets or component geometry were hand repaired.
The proposed role catalogs remain supplied test inputs, not autonomous part discovery.

## Actual outcomes

| Case | Interpretation | Construction / repair |
|---|---|---|
| Original generic drone | Exhausted the unchanged 3,072 output-token allowance; incomplete inventory retained. | Never planned or built. No inference or geometry pass. |
| Three cooling fans | Both groups correctly declare an equally spaced horizontal row and forward-facing axes. Counts and inspection intent survive. | Seven generated parts. Initial feature and symmetry failures; one repair fixes those but leaves two islands in each frame, insufficient shaft overlap and all six axes pointing backward. Final failure. |
| Two-driver speaker | Two drivers side by side, both forward, with inspection and separation. | Required “drivers in enclosure front face” remains unsupported by the existing spatial registry. Correctly blocked before planning. |

The fan output is a recognizable row of fan-like parts, with basic materials and
simplified geometry. It is not a coherent, fully supported mechanical assembly:
mounting tabs become disconnected and the rim/rotor relationship does not establish
a meaningful central support. No polished-object, engineering, motion or Quest pass.

[Interactive fan review](http://127.0.0.1:8775/assembly-run-010/?case=cooling-fan-row-plan-1)
contains both unchanged attempts. The desktop viewer shows failed construction as
failed and supports selection, separation and reset. Animation is disabled.

## What the experiment establishes

- Every declared repeated entity needs placement and orientation decisions. Unplanned
  repetition cannot bypass the coverage gate by omitting its count requirement.
- Decisions refer to existing source-bound requirement IDs. Group membership, patterns,
  object frame, tolerances and admitted feature bindings remain fixed across repair.
- Shared signed directions differ from undirected parallelism. Equal-radius radial
  patterns differ from straight rows. Outward-pointing members reuse the existing
  radial-orientation checker instead of being forced to share one global direction.
- Actual solved geometry supplies feature centers and axes. Checks identify the group,
  requirement and individual members. The old drone's two misoriented motors fail a
  synthetic offline negative-control constraint with its geometry untouched.
- The fan repair's layout passes while orientation fails: all six axes have alignment
  -1 against requested +Z. Correct local connections do not waive that group failure.

These are declared-relationship checks. They cannot establish that the model inferred
all necessary relationships or selected the correct semantic feature. A source quote,
a complete ID list and a visible cylinder are not proofs of understanding or function.
The bounded tests do not support describing the entire understanding layer as solved.

## Separate failure classes

The first fan attempt has numerically aligned axes and equally spaced feature centers,
but those selected features fail the existing geometry tests. Its group checks must
therefore fail too; it is not honest to label the features verified.

After the paid batch, diagnostics were enriched to distinguish supporting-feature
failure from placement/orientation failure. Offline replay against the unchanged
plans and compiled meshes preserves every original verdict and tolerance. The first
attempt is classified as feature-geometry failure; the repair as group-orientation
failure, with connectivity and overlap failures reported separately. Original reports
and the diagnostic replay are both retained. No third plan or additional paid repair.

The drone's 3,072-token response used 1,572 reasoning tokens and about 1,500 output-text
tokens. The retained partial text stops during requirement 31, before completing the
inventory and assembly decisions. This is a response-capacity failure, not funding
exhaustion. No output limit was raised and the incomplete response was not retried.
The speaker exposes a distinct vocabulary gap: front-face placement is more specific
than facing forward or belonging to a linear row. It was not silently replaced by those.

## Cost and verification

| Operation | Usage-derived estimate | Provider response time |
|---|---:|---:|
| Drone interpretation, incomplete | $0.0395275 | 36.53 s |
| Fan interpretation | $0.021855 | 15.87 s |
| Speaker interpretation | $0.0223025 | 16.29 s |
| Fan initial plan | $0.05638 | 59.78 s |
| Fan repair | $0.062135 | 40.08 s |
| Total | **$0.2022** | 173.16 s total batch elapsed |

These are conservative calculated estimates, not provider invoices. No GPU spending,
funding errors or new uncertain reservations occurred. The shared daily $6 allowance
has $3.185155 remaining; that is not the provider credit balance. Old $0.25535 uncertain
holds remain. The $1.10 batch ceiling and $5 aggregate ceiling were respected. Use a
conservative $4.00 prior allowance for a future research batch; do not erase old holds.

152 targeted test executions pass (including inherited tests): source/contract guards,
group coverage, invalid axes/features, root-frame invariance, spacing, repair locks,
spending and the unchanged geometry regressions. Nine browser checks pass, with zero
page errors. Frozen live-run commit: `6cd6068`. Subsequent code changes only enrich
failure diagnostics; replay proves unchanged verdicts on both saved outputs.

## Next decision

Keep the group decision/check layer, without claiming broad generation success or
expanding to six new layout families. Three independent issues remain:

1. Keep the drone's necessary intent within a complete structured response. Audit
   redundant/verbose requirement and decision transport before increasing limits;
   do not omit requirements merely to fit.
2. Represent generic placement on a declared object surface, including front-facing
   surfaces. Preserve the speaker's missing relation, then test it on unrelated parts.
3. Improve construction repair so it preserves passing group direction and connectivity
   while fixing feature geometry. The fan shows a measured repair regression, not a
   reason to weaken validation or switch models blindly.

The current cross-family comparison remains incomplete. Another paid batch should
follow a concrete change addressing one of those failures, with the same cases and
fixed acceptance criteria. No further spending was needed to document this boundary.

[Protocol](ASSEMBLY_EXPERIMENT.md) · [Retained evidence](results/assembly-010.json).
