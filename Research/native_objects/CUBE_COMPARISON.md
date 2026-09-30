# Cube geometry bridge 001 — frozen before GPU execution

Question: can a whole-shape generator followed by named-part synthesis realize
unchanged ORYN component proposals across different concepts, without per-output
repair? A good plan or matching filename is not a successful generated object.

## Capability audit and route

Selected for a bounded research comparison: Cube 3D v0.5 text-to-shape, followed by
CubePart mesh-plus-part-names synthesis. Code revision and five model/config
revisions are frozen in [the machine-readable protocol](cube_protocol_001.json).
The [released CubePart instructions](https://github.com/Roblox/cube/tree/3c6d06ddbef3160a1e1950cb13ab63dd12a61e50/cubepart)
require an input mesh; the text-to-parts description alone is not a released direct
text-to-parts adapter. The [pipeline source](https://github.com/Roblox/cube/blob/3c6d06ddbef3160a1e1950cb13ab63dd12a61e50/cubepart/cube_part/pipelines/shape_denoiser.py#L196)
allocates **eight part slots**. Do not merge, truncate or retry a plan to fit it.

The repository [license](https://github.com/Roblox/cube/blob/3c6d06ddbef3160a1e1950cb13ab63dd12a61e50/LICENSE)
is research-only; package metadata is inconsistent with that license. This is an
isolated evaluation, not adoption into ORYN's commercial product.

- Drone: seven named groups, eligible. Repeated motors/propellers remain groups;
  the adapter does not manufacture individual instance IDs or repair geometry.
- Speaker: nine named groups, unsupported before dispatch. Keep this as a failure
  of coverage, not as a skipped success. No paid generation for this case.
- Exact JBL: blocked by the plan's evidence requirement; no paid generation.
- Leaf/seed lamp: five named groups, eligible.

The first-stage text is exactly the planner's object description. Second-stage
names are exactly its component names. All cases share code and parameters.
No model-generated component name is treated as verified semantics. The whole
shape may omit interiors; whether part synthesis can realize them is an open test.

## Fixed run and budget

One seed (0), no retries or alternate prompts; no manual repair, reorientation,
simplification, slot-count edits, component merging or seed search. The worker
seeds Python/NumPy/Torch; upstream sampling and GPU arithmetic are not guaranteed
bit-reproducible. Preserve whole meshes and every requested part's status/hash,
even if it is absent. Upstream center/scale normalization is recorded; canonical
orientation is assumed from generation and must be checked visually.

Two eligible objects, two stages each, one attempt each. Each stage has a 20-minute
timeout. One A100 80 GB rental, at most $1.59/hour, at most two hours, 100 GB
of ephemeral disk, and a $3.50 estimate ceiling. Two-hour compute plus disk is
about $3.21 at the checked rates. This stays below the earlier $5 research ceiling
including the approximately $0.1541 spent on PartCrafter. End the rental as soon
as outputs or failures are downloaded. No persistent/network volume.

A separate local process keeps the Mac awake and explicitly deletes the pod at
the deadline or early-completion signal. This depends on connectivity and is not
a provider-enforced monetary cap. Unknown creation outcomes must be reconciled
by listing the unique pod name, never blindly creating another rental. Check the
account for leftovers after deletion. Model downloads and dependency setup count
against the same rental window. Provider invoice amounts may lag estimates.

## Predeclared scorecard

Review original whole shapes and assembled/exploded part views for both eligible
objects, using the same neutral rendering. Score each dimension 0 (fail), 1
(partial), or 2 (pass), with observations:

1. Concept: whole and reassembled output clearly preserve the requested form.
2. Coherence: no major missing shapes, floating debris or severe malformed geometry.
3. Role coverage: every requested role has nonempty, plausible geometry; labels alone
   do not establish coverage. Count missing/extra/fused roles explicitly.
4. Separation: major requested roles can be selected independently. For the drone,
   count physical motor/propeller pieces separately from GLB groups; group selection
   does not demonstrate per-instance selection or useful internal electronics.
5. Assembly: generated parts remain in a sensible common frame and fit plausibly.
   Do not count this visual check as measured collision/clearance validation.

Missing output cannot pass. A geometry case passes only at 2 on all five criteria,
zero repairs, and unchanged static import preflight. Runtime/Quest, materials,
joints, physics and animation stay unassessed. Oversized output may be inspected
with the existing offline opt-in, retaining the production failure.

Overall cross-object success requires every generic/creative plan to be supported
and pass. The speaker incompatibility already prevents that result for this pinned
release. If both eligible cases pass, report **partial coverage** and decide whether
further research merits a separately approved/frozen test. If either is unusable,
stop this configuration without more seeds or a one-off repair. Infrastructure
failure is inconclusive geometry evidence, not a semantic failure or model ceiling.

## Local reproduction

`cube_bridge.py` previews compatibility without credentials, network or GPU work.
`cube_worker.py` runs only the explicitly eligible research cases on a prepared
isolated worker. Original production generation/execution flags stay false.
No Quest route, new object format, answering work or autonomous provider discovery
is introduced. Fifty earlier planning/provider tests and five new capability
checks verify contracts only; live geometry assessment remains separate.
