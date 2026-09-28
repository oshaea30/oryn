# Persistent workflow and fast-decision baseline

Checkpoint: 2026-09-27. ORYN runs this code as part of ingestion; Codex does not
make the individual routing decisions. This is the **local baseline**, not a
completed autonomous researcher or an installed Jev integration.

## Current increment: approved live reference research

The user approved the outbound-data and spending scope on 2026-09-27. The local
object-request service now owns a separate research worker. New object requests
automatically queue research after ingestion without holding model delivery for
external work. Existing assets can use **Research this saved object**; this is an
operation request, not an approval dialog. Startup does not research an old asset
that was never queued.

`research_providers.py` implements a fixed-host Wikipedia adapter and a separate
OpenAI cognitive adapter. `research_service.py` connects them to the persistent
executor, UI and existing shared cognition ledger. Retrieval returns up to five
truncated introductions in search rank order; at most three non-rejected
candidates reach synthesis. Wikipedia is secondary discovery material, not an
authoritative schematic source. Object/revision matches start unknown. No exact
revision claim is made from an article's title or retrieval time.

The OpenAI adapter uses `gpt-6-sol`, the existing reviewed `question` profile,
tools-free structured output, exact input counting and a 1,024-output-token cap.
The ceiling is $0.05 per investigation, sharing the existing $2/day ledger with
command cognition. Reservations precede dispatch. Timeouts retain reservations;
unreconciled model/tier/usage halts paid cognition. No automatic retries, fallback,
model escalation, hosted search tools, room images, GLBs or local paths are sent.
User descriptions, selected excerpts and two geometry counts are the payload.
Prices still expire on 2026-10-04; this integration does not silently extend review.

API shape and rates were checked against official documentation:
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol).
Retrieval follows the [MediaWiki TextExtracts API](https://www.mediawiki.org/wiki/Extension:TextExtracts).

OpenAI research uses ORYN's Keychain service `com.oryn.local-generation`, account
`openai-api-key`, distinct from `meshy-api-key`. `ORYN_OPENAI_API_KEY` is an optional
process-only override. The separate command service's existing memory-only key is
not extracted or erased. Saving the research connection resumes only synthesis
that has never been attempted; it does not refetch sources or retry paid failures.

Verification: 187 backend tests and the mocked browser checks pass. The live V8
run `f2eaf33ba412140ead0149fa1fd5538c417459e44181ea81182a14bfe42019e4`
retrieved five references, retained all five, and selected three for synthesis.
It initially stopped at `awaiting_cognitive_provider`. After the user saved the
research key, ORYN automatically resumed and reached `reference_notes_ready`.
The synthesis stage took 12.021 seconds (including count/admission/response and
validation) and the shared ledger recorded a conservative usage estimate of
$0.0065725 against a $0.0117825 reservation. Actual invoice cost remains unknown.
The result cited sources, distinguished general V8 knowledge from specific Rover/
Porsche examples, and preserved unknown identity, revision, internal completeness
and mesh mappings. No geometry was labeled or promoted to verified knowledge.
This proves one live application-owned research run, not general mapping quality.
The key is persisted in Keychain. No models were regenerated, delivered or modified
by the research check.

### Durable investigation executor

`Orchestrator/investigation.py` now implements a separately testable, durable
research queue with `RetrievalProvider` and `CognitiveProvider` interfaces. It
claims each run transactionally, saves stage state before provider invocation,
retains up to five reference candidates, triages them through the existing
fast-decision boundary, and passes at most three candidates to synthesis.
Interrupted/failed external work is never automatically retried. Missing
providers have explicit blocked states; only unattempted work can resume after
provider configuration.

Findings validate citation membership and remain object-family candidates with
no geometry mappings. Source snapshots carry content hashes, retrieval times,
object/revision match states and citation links. All supplied candidates remain
auditable even when rejected or deferred. Unknown cost cannot be stored as zero.
This does not prove that a cited excerpt supports a claim; entailment review and
visual component identification remain separate work.

The first executor increment was offline-only (167 tests). Live integration was
initially stopped for a one-time permission decision; that permission is now
granted and the integration above supersedes the earlier blocker.

## Ownership and boundaries

| Responsibility | Owner | Current implementation |
| --- | --- | --- |
| Idempotency, budgets, hashes, import limits, capabilities | Deterministic ORYN code | Active; a decision cannot override them |
| Exact saved match vs generation | Fast-decision contract + local rules | Active in object requests |
| Piece prioritization | Fast-decision contract + local rules | Active after ingestion |
| Geometry acquisition / device delivery | GenerationProvider / transport | Existing Meshy / ADB implementation, unchanged |
| Reference retrieval | External worker | Wikipedia discovery connected; five candidates maximum |
| Reference relevance / object / revision triage | Fast-decision contract | Local metadata rule active; unknowns reach bounded investigation |
| Evidence synthesis / hard mapping / novel reasoning | Separate cognitive investigation worker | Bounded reference synthesis verified on one live V8 run; hard mapping not implemented |
| Evidence validation and knowledge publication | Deterministic ORYN code | Manifest validation exists; publication from investigation is not implemented |

`Orchestrator/fast_decisions.py` defines the provider-neutral
`FastDecisionProvider`. Inputs are bounded facts and stable IDs; output is exactly
one `{id, action, reason_code}` per item. Omissions, duplicate/foreign IDs, unknown
actions and extra fields are rejected. There is no confidence decimal, tool call,
provider-specific action or permission to spend in the result.

`POINTS` marks **active**, **contract_only**, and **planned** decisions explicitly.
Representation depth, component-family proposals, evidence sufficiency and
semantic exposure are planned seams, not implemented capabilities. The current
object-request route still uses an exact normalized prompt match; there is no
semantic library search or automatic retrieval fallback.

## Application flow today

1. Validate the request, available assets, backend budget and operation gates.
2. Persist the request and its local library/generation routing decision.
3. Acquire geometry through the existing route; paid calls never auto-retry.
4. Inspect and ingest it into the existing immutable manifest.
5. Persist local measurements, a bounded geometry-triage batch, and remaining
   investigation steps in `.oryn-generation/workflows.sqlite3`.
6. Deliver the supported representation without waiting for research. Failed
   investigation preparation does not erase the model or prevent delivery.

Cheap local triage and durable queue admission are synchronous before delivery.
External research runs on its own worker, independently of delivery. Its progress,
sources, unknowns and available notes appear in the Object Research panel.
There is no autonomous retry loop. Research records do not modify live transforms,
ingestion capabilities or the component graph.

Each investigation is bound to the asset hash, manifest content/revision and
workflow version. Reusing identical geometry/knowledge reuses its analysis even
if the generation job ID differs. Changed evidence creates a separate record.
Restart/backfill performs only missing local preparation; it does not regenerate,
resend models, fabricate historical decision timings, or alter reservation dates.
Interrupted preparation remains visible and is not automatically replayed.
The current store is for one local service process, not a distributed job queue.

## Geometry baseline and V8

The first baseline uses existing local bounds and triangle counts. It ranks
missing measurements first, then descending triangle count with a stable ID
tie-break. At most **eight pieces per asset revision** are prioritized for later
investigation. This is a tunable workload limit, **not** evidence of mechanical
importance; a tiny crucial part may be deferred. No geometry is thrown away.

On the saved assets, offline verification found:

| Asset | Pieces retained | Prioritized | Preserved unknown / deferred |
| --- | ---: | ---: | ---: |
| Drone | 39 | 8 | 31 |
| V8 | 200 | 8 | 192 |

All remain semantically unidentified. The V8 still has no supported flat
200-target explosion; that runtime limitation is not solved by prioritization.
Neither GLBs nor ingestion manifests were changed by the decision pass.

The local baseline record separates deterministic measurements, fast triage,
external retrieval, reference triage, deep investigation and evidence validation.
Its original `awaiting_research` marker is a baseline checkpoint, not live worker
state. Current progress is stored in the separate `research_runs` record linked
by each job's `research_id` and exposed as `job.research` in `/api/state`.
Missing research credentials are visible, not an endless “researching” spinner.

## Instrumentation and outcomes

Every decision record contains contract/provider/version, input snapshot, stable
scope, results, timestamps, batch latency, explicit cost status and initial
`unreviewed` quality outcome. The local rules have known **zero provider cost**.
That is not the cost of generation, storage, delivery or future research. Unknown
provider billing is never recorded as zero. The research adapter reports a
conservative usage estimate separately from actual invoice cost, which remains
unknown. Failed/uncertain billing is exposed from the shared durable ledger.

Latency currently measures rule execution plus contract validation, excluding
SQLite persistence. It is neither Meshy latency nor end-to-end request time.
Per-item timings are not invented by dividing a batched call. Result counts and
failures are retained; contract-valid JSON does not establish decision quality.

`WorkflowStore.evaluate()` accepts separately labeled expected actions with an
evaluator/revision identity. Append-only match/mismatch records are separate from
the original decisions. They evaluate routing, not component truth or mechanical
verification. There is no HTTP writer that lets a client promote knowledge.

Read-only local diagnostics:

- `/api/workflow?id=<investigation-id>`: steps and replayable decision records.
- `/api/workflow-metrics`: aggregate local decision timing, cost and outcomes.
- The object request UI links its saved investigation and reports its blocker.

These diagnostics use the existing loopback/Host restriction. Keys, headers,
signed URLs and raw provider exceptions are not decision inputs or log fields.
The SQLite file is ignored by Git; no files are uploaded to cloud storage.

## Local geometry evidence checkpoint

Implemented 2026-09-28 in `Orchestrator/geometry_evidence.py`. A dedicated local
background worker runs independently of generation delivery and paid research.
Startup backfills a local queue for saved generated assets; new objects enqueue
after ingestion. It does not upload, regenerate, invoke a provider or send Quest
commands. Asset/source/manifest IDs and exact face membership are checked again
before rendering. Views and measurements persist in the ignored workflow SQLite
store, independently from immutable interaction manifests.

- All supported pieces get fresh local bounds/triangle/vertex measurements.
- Up to eight baseline investigation targets get four orthographic context views
  plus four isolated views. Full source-local orientation/transform provenance is
  retained. Views use deterministic painter-order SVGs; they are not photos,
  engineering drawings, z-buffer-accurate captures or model-ready raster inputs.
- Nearest bounding-box gaps are lower-bound spatial measurements, **not** surface
  adjacency, component identity or evidence of mechanical attachment. No assembly
  groups or semantic labels are inferred from them.
- Narrow layout support intentionally matches the lossless decoder: position-only
  indexed triangles in one static mesh node. Unsupported layouts remain unchanged
  with an explicit unavailable status, never a silent attribute-dropping conversion.
- Work bounds: 20,000 triangles, 2,048 recorded pieces, eight viewed targets,
  16 MiB/view and 64 MiB/package uncompressed, 256 MiB aggregate compressed view
  storage. Preserve a 576 MiB free-space floor before preparation. No eviction.
  Compressed SVGs have bounded decompression and are SHA-checked before serving.
  SQLite freed pages may remain allocated for reuse; this is not cloud storage.
- Content-addressed reuse and transactional claims avoid duplicate work. Running
  work interrupted by restart is marked interrupted, not silently replayed. Local
  errors never invalidate an existing model or trigger a paid replacement.
- `/geometry-evidence?id=…` is a read-only inspection page. The object request UI
  links it. `/api/geometry-evidence` returns measurements/view hashes without local
  filesystem paths; `/api/geometry-view` returns one checksum-bound SVG.
- `MappingCognitiveProvider` defines a separate future vision boundary. No live
  adapter or HTTP mapping writer exists. The strict result contract requires each
  selected piece to be a reference/view-linked candidate or explicitly unknown.
  Unknown/duplicate IDs, wrong views/citations, fake confidence and epistemic
  promotion are rejected. Each accepted candidate carries model/operation
  provenance and `not_reviewed` status. Revisions are idempotent and append-only;
  they do not upgrade manifests or interaction capabilities.

Live local check: V8 200 measurements/eight view sheets, drone 39 measurements/eight
view sheets; both ready in about 1.1 seconds before the later compression change.
The real V8 page was browser-rendered and visually inspected. Source geometry,
completed V8 reference notes and Quest capabilities were unchanged. All component
identities are still unknown. Tests use synthetic candidates, not claimed V8 labels.

## Next implementation and benchmark gates

1. Extend the local evidence package into bounded raster inputs for live vision;
   evaluate preview occlusion artifacts before treating them as model evidence.
   Actual surface adjacency remains future work; AABB proximity is not a substitute.
   Sending rendered images would expand the current outbound scope and requires
   a separate image-data/cost policy before any live vision call; room imagery
   remains out of scope.
2. Use visual/structural evidence plus references to propose candidate mappings,
   with explanations and explicit unknowns. Keep suggestions reviewable and
   preserve corrections; never infer a verified identity from appearance alone.
3. Evaluate source relevance and factual support with labeled examples. Add richer,
   authoritative references and group pieces into assemblies before enabling
   a 200-piece V8 take-apart experience under the 64-active-target runtime limit.
4. Validate evidence and write a new knowledge revision; never overwrite a good
   interaction manifest or silently upgrade an epistemic state. Publish progress
   independently from geometry delivery. Preserve user transforms during updates.
5. Capture representative, labeled decision fixtures from that working baseline:
   exact vs near matches, revision conflicts, missing data, small critical pieces,
   misleading geometry and sources, and abstention/escalation cases.
6. Only then add experimental Jev behind `FastDecisionProvider` and a reviewed
   spending gateway. Replay the **same inputs and labels** against local rules,
   the chosen existing model provider and Jev. Record model/config versions,
   p50/p95 batch latency, actual cost, malformed/timeout rate, agreement with
   labels, important-case false negatives and escalation volume. Include deep
   follow-up costs and end-to-end time; a cheap wrong shortcut is not a win.
7. Use shadow evaluation first. Production switching requires demonstrated quality
   and savings, with abstention and a bounded escalation path. A timeout or malformed
   result must not trigger an unlimited fallback/retry cascade.

No Jev dependency, external fast model or paid benchmark has been added.
Jev cannot reduce Meshy's generation time. Provider speed claims
remain unmeasured until the controlled comparison exists.

Cloud-backed durable assets and bounded caches remain the storage direction in
ORYN_ROADMAP.md; this increment neither provisions storage nor evicts local assets.
