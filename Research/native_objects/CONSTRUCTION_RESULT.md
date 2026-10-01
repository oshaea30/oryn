# Procedural construction 001 — measured result

**Partial structural progress; finished-object quality failed.** One application-owned
model policy generated all object-specific dimensions and positions for four requests.
No numerical rescue, manual geometry repair or paid retries. This does not establish
that arbitrary objects can be generated correctly.

Frozen implementation: `442724d`. [Protocol](CONSTRUCTION_EXPERIMENT.md).
[Full result and scorecards](results/construction-001.json).

| Request | Instances | Declared numeric relationships | Coarse file ready | Visual score /10 |
|---|---:|---|---:|---:|
| Drone | 19 | 18 mounts, 4 gaps, 8 symmetry bounds pass | 55.04 s | 9, fails role fidelity |
| Speaker | 11 | 10 mounts, 3 containments, 3 gaps, 2 symmetry bounds pass | 51.14 s | 7 |
| Leaf/seed lamp | 5 | 4 mounts, 2 gaps pass | 30.82 s | 8 |
| Unfamiliar pencil sharpener | 6 | 3 mounts, 2 containments, 1 gap pass | 39.76 s | 5 |

All five visual dimensions must score 2/2; a high total cannot override a failed
criterion. Exact JBL reconstruction remained evidence-blocked with no geometry call.
The pencil-sharpener request was chosen after freeze; its six role groups came
from the existing application planner, not a hand-written component recipe.

## What the outputs establish

The deterministic builder can realize model-selected dimensions, placement and
separate component identities. The model produced numerically consistent declared
relationships across all four examples. The speaker retained its full nine-role
plan, unlike the earlier eight-slot Cube limitation. Original proposals, relationship
reports, checksums and inspection sheets are retained under
[results/construction-001](results/construction-001/).

The outputs also demonstrate why numerical passes are insufficient:

- Drone: repeated motor/propeller instances are separate and consistently positioned,
  but electronics are undifferentiated blocks and blades are crossed ellipsoids.
- Speaker: internal blocks fit the cavity. The grille and charging port are solid
  proxies; no matching port opening exists. Discs stand in for driver/radiator shapes.
- Lamp: a coherent five-part chain, but a thick leaf-like solid with a seed below it
  only partially captures the requested seed *inside* a curled leaf. Glow is absent.
- Sharpener: guide ends at a closed wall; drive is not connected to cutter. Containment
  does not supply a mount or drive path. **Semantic assembly coverage fails** even
  though every declared numeric check passes. The model disclosed several limitations.

The first three provide partial structural-control evidence. The unfamiliar case
fails semantic connections. None passes the product visual gate, and no output is
promoted to production or Quest. These are illustrative proposals, not engineering.

## Latency, cost and interaction

The model request took 30.81–55.00 seconds. Coarse build/check/export took 0.011–0.040
seconds; fine tessellation took 0.011–0.067 seconds. Those are local measurements,
not guarantees. Role planning was replayed; the sharpener's separate role-planning
call took 6.71 seconds. No end-to-end client-delivery or hosted cold/warm measurement
was made. File-ready is not time-to-useful, which remains unset because the visual
usefulness gate failed. The 30-second target was not reached even at file-ready.

Estimated model cost: **$0.19322**, including the new role-planning call, against
$0.53 maximum for this experiment. No GPU rental. Provider invoiced cost is unknown.
All requests used existing credential handling, reviewed rates and the shared ledger.

All four cases preserve IDs, roles, parents, selection and explosion amount across
12-to-24-segment tessellation. This is deterministic mesh-detail change, **not**
generative polishing or evidence that a neural refiner will preserve structure.
Reset works; unsupported animation remains disabled. Thirty-five Python checks and
four browser cases pass. Depth-buffer rendering was added after an inspection issue
made inner parts appear through opaque walls; original model geometry was unchanged.
The occlusion test checks near/far triangles in both draw orders.

## Decision

Preserve the demonstrated application-owned spatial control, but do not treat this
primitive vocabulary or numeric checker as the final generator. Stop this batch with
its failures intact. The next decision should address the observed gap: general
interface geometry (openings and joined surfaces) plus checking whether essential
connections were omitted. A constrained appearance experiment remains a separate,
unproven capability. No additional paid calls, automatic feedback loops, model
training, new object format, answering or animation work were started.
