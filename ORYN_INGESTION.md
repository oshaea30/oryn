# ORYN object ingestion — v1

The canonical local record for each source GLB is `<variant>.ingestion.json`,
beside that GLB in its ignored generation-job folder. The original bytes remain
unchanged. A supported derived assembly is `<variant>.assembly.glb`. No provider
calls, uploads or automatic paid repairs occur during ingestion.

## Contract

- `asset_id`: source GLB SHA-256, stable across reuse/jobs.
- `schema_version`, `revision`, `pipeline`: explicit versioning. Existing manifests
  are validated/reused, not silently regenerated or overwritten. No migration or
  semantic editing API exists yet.
- `source_geometry`: checksum, counts and node transforms. Piece bounds are in
  source-node local coordinates, not arbitrary world coordinates.
- `geometry_pieces`: stable source-hash + island IDs, bounds, triangle indices and
  runtime node bindings where separable. Connectivity preserves triangle winding,
  coordinates and transforms. No cuts, near-position welding or invented surfaces.
- `components`, `component_mappings`: currently empty. Geometry is not anatomy.
- `assembly_hierarchy`: a geometric container referencing every recorded piece.
  This is the starting structure, not an inferred semantic hierarchy.
- `evidence`: measurable source facts, including index connectivity and exact-position
  connectivity counts; these can differ at seams. No fake numerical confidence.
- `unresolved_mappings`: all unidentified pieces remain explicit.
- `capabilities`: supported/unsupported plus a reason. Geometric isolation is distinct
  from component isolation; no semantic explanation or verified internals are claimed.
- `provenance`: originating job, provider/profile, task and reuse relationship. No keys,
  signed provider URLs or absolute storage paths enter the manifest.
- `runtime`: selected source/prepared representation, its checksum, active target
  budget and validation scope. `headset_verified` remains false: an import receipt
  alone does not verify interaction behavior or mechanical correctness.

Future mappings must explicitly supply `geometry_ids`, `component_id`, an epistemic
state, `derived_by`, evidence IDs and `human_review.status`. Allowed states:
`unidentified`, `candidate`, `reference-supported`, `verified`. Model-derived mappings
require provider/model provenance. Reference-supported records require an identified
reference source. Verified records require evidence and a verification method.
The validator enforces record structure; it cannot establish that cited evidence is
true or that a human/model classification is correct. No transition is automatic.

## Current geometry coverage and runtime policy

The deterministic separator supports the same narrow, static, indexed, POSITION-only
geometry layout used by the drone and V8. Unsupported attributes/layouts are retained
unchanged; native mesh-node records are used instead, with the limitation recorded.
Native static multi-node models may already fit the runtime assembly contract.

For supported connectivity analysis, **all pieces** are recorded, even above the
64-active-target Unity limit. Only 2–64 pieces are automatically exported as a flat
interactive assembly. Above 64, the source remains a whole object and take-apart is
explicitly unavailable. We do not delete fragments, group them by guessed anatomy,
or increase the Quest interaction budget. Hierarchical/semantic LOD is a future
runtime feature, not a graph-size restriction.

## Integration

Generation/reuse → source preflight → ingestion → supported assembly preparation →
manifest-bound delivery → Quest import receipt. No user approval steps added.
The existing Unity assembly wrapper recognizes the separated renderers; no Unity
code or rebuild is needed for this increment. The full manifest currently lives on
the Mac. Quest receives the selected GLB through the existing checksum-bound inbox;
the language command service does **not yet query** this manifest.

Service startup backfills saved variants locally, preserving original geometry,
existing manifests, delivery receipts, annotations and job timestamps. It never
delivers or regenerates on startup. Annotation records bound to an earlier derived
GLB are not silently rebound to a new export; source-hash geometry IDs provide the
foundation for an explicit future migration.

The UI separates model-loaded status from take-apart preparation. A historical
source-model import does not count as loading its newly prepared assembly.
Capability summaries are shown both in the request screen and developer lab.

## Evidence for this increment

- Drone source: 39 disconnected islands, all represented, 39 prepared targets.
  Exact triangle multiset/winding and source node transforms preserved in export.
- V8 source: 200 disconnected islands, all represented, zero identified mechanical
  components. Whole-object path retained; geometric take-apart unsupported at this
  runtime level. No claim that expected engine internals exist or are complete.
- Offline tests cover stable IDs, lossless export, native multi-node preservation,
  the 200-piece boundary, provenance validation, checksum tampering, immutable
  manifest reuse, automatic prepared delivery and restart without duplicate delivery.
- Browser tests check V8 limitations and prevent an old source receipt from claiming
  the prepared drone is loaded. Live Quest behavior for this new path remains a
  separate hardware check; earlier drone interaction tests do not prove this build.

Live follow-up: the automatically prepared drone passed the headset-guided
explode/reassemble test on 2026-09-27. All 39 targets restored and Quest acknowledged
the terminal result; report `.oryn-inspection/guided-2SB7zs/report.json`. This validates
command-level geometric interaction, not component identity or mechanical accuracy.
The immutable v1 ingestion record remains a static-preflight record; this live test
is separate evidence, not an automatic semantic verification upgrade.

Next: evidence-backed component plans/mapping and hierarchical interaction.
Do not relabel the V8's geometric pieces as engine components without that work.
