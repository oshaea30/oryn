# Executable connections 003 — frozen bounded test

Question: can the current application-owned model use geometry-backed interfaces
and deterministic placement to produce better constrained assemblies, then correct
its geometry without changing the requirements? This extends the existing research
plan and output package. It does not introduce a public format or CAD rewrite.

## Actual implementation boundary

- Face ports select additive box/rounded-box faces or solid-cylinder caps. The
  executor derives a central finite patch, frame and outward normal. Solid probes
  on either side verify that the patch remains present and exposed after booleans.
- Axis ports select circular cylinder/tube geometry and a finite axial interval.
  Solid bands establish an exposed outer cylinder or a surrounded, unobstructed bore.
- Face mates calculate relative rigid placement with opposing normals, separation
  and twist. Coaxial mates align axes and check radial clearance and axial engagement.
- One root anchors a connected graph. Extra relations are checked for incompatible
  cycles. All part pairs are checked for positive-volume interference. Existing
  identity, containment, declared clearance and symmetry checks remain active.
- A serialized requirement contract locks parts/roles/parents, logical port bindings,
  all mates and existing geometric requirements before first compilation. Geometry
  and feature selectors may change during one correction; requirements cannot weaken.
- Separate axes do not establish mechanical coupling or motion. Central patches are
  not full-face congruence proofs; finite bore intervals do not prove an entire feed
  path. The solver cannot establish that essential requirements were not omitted.
- Intentional interference, noncircular axis fits and arbitrary loft-surface ports
  are unsupported. Static structural evidence is separate from finished visual quality.

Synthetic fixtures use no object recipes. They test placement, rotated/reversed
relations, true gaps/engagement, buried/deleted faces, blocked/nonexistent bore
intervals, incompatible cycles, all-pair interference and forbidden requirement edits.
Those fixtures are engine tests, not claims of model generalization.

## Fixed live protocol

Same four generic/creative requests and replayed role plans as solid-002. Exact
JBL stays evidence-blocked. The sharpener is known, not a fresh held-out object.
Model: existing gpt-6-sol high; 12,288 output tokens; $0.16 per-request admission cap.
No paid visual-review calls. Feed deterministic failures or bounded compiler errors
back to the application model for at most one repair. No manual corrective values.
Invalid first contracts stop a case, since no reliable requirements can be frozen.
No retries for ambiguous delivery. Uncertain costs remain reserved. Shared ledger
model/tier/usage and price-expiry checks remain fail-closed.

Experiment cap $0.90, including uncertain reservations, under the shared $2/day and
aggregate $5 research ceilings. A conservative $1.60 prior-research allowance includes
prior GPU estimates and model costs/held reservations. This cap can prevent later
repairs; missing attempts are not a geometry-quality failure. No GPU deployment.

Response timeout is 240 seconds rather than solid-002's 120; response size bounded
at 256 KiB. Safe failure categories and elapsed dispatch time are retained. This is
an explicitly changed delivery condition, not evidence of model improvement. Keep
instructions, schema, executor and requests frozen before execution; record hashes.

Record model request latency, connection compilation, combined build/validation,
render-ready and cumulative time through repair. Combined stages are labeled as
such, not attributed to geometry alone. Replay planning, export/render and network
limitations remain visible. 30/120-second targets remain product pressure; slower
structural candidates are research evidence, not product passes.

## Decision

A numerical pass means only that all declared supported requirements were realized.
Inspect actual geometry and essential connection coverage independently. Compare
with the prior failures descriptively; changed representation, checks and transport
prevent a clean causal model comparison. Preserve failed initial and revised outputs.
A promising structural result warrants a frozen unfamiliar-case test; no model swap,
training, generative refinement, product integration or additional spending is automatic.
If the representation fails to express required interfaces, report its limits before
adding new primitives. If plans omit essential relationships, preserve that as a
planning/coverage failure rather than hand-authoring those relationships for the model.
