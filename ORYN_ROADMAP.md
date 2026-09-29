# ORYN working roadmap

Last checkpoint: 2026-09-28. This file records the agreed direction so new ideas
do not silently replace the current milestone.

## Product goal

Request an object in natural language, obtain or generate geometry, interact with
it spatially, and investigate it using persistent, evidence-backed knowledge.
Geometry generation and object understanding are separate responsibilities.
Generated shapes and user labels must not become verified mechanical facts.

## Proven checkpoint

- A live geometry-only drone generation/download and Quest import worked.
- The drone can be manipulated, exploded and reassembled with existing controls.
- Saved part annotations and a guarded text-command transport are implemented.
- Live automated command tests verified explode/reassemble and selection/isolation/
  restoration on the 39-part drone, using execution receipts plus scene checks.
- Isolation observations validate active flags, not rendered visibility. Inactive
  transforms are unavailable through the installed Operator and are checked after
  restoration. These tests do not prove gesture feel or semantic understanding.
- OpenAI interpreted "Put everything back together" as reassemble in 1.7 seconds.
  After the user confirmed, Quest executed it and independent inspection verified
  all 39 parts restored in position, rotation and scale. This proves one live case,
  not general interpretation quality or semantic understanding.

## Current milestone: mechanical behavior / MVP 1

See [mechanical foundation and verification gates](ORYN_MECHANICS.md). A reusable
deterministic schema/evaluator, separate authored drone/V8 teaching fixtures,
desktop viewer and headset controls are implemented. Runtime/editor code compiles;
an isolated Unity solver run passed 11,576 checks. On 2026-09-29 the full-project
mechanical/workspace/menu/command/synthetic-assembly tests passed, and both rendered
fixtures were inspected. ORYN 1.12.0/code 15 is now built, signature-checked, installed
on Quest 2 and launched with live state/hand-grab logs. The user has now visually
confirmed drone play/slow/pause and V8 synchronized motion, slow/pause and continued
motion during subsystem isolation. This bounded authored-demo headset checkpoint
is complete, not verification of generated anatomy or general physical accuracy.
Stop before another major intelligence subsystem and reassess MVP 1 scope.
No generated meshes have been falsely bound to presumed mechanisms.

The explicitly authorized second reference pass used a targeted Fel-Pro manufacturer
excerpt. ORYN completed one bounded object-only comparison: both upper-cover
hypotheses were tentatively consistent, **still candidate**, with underside/contact
checks outstanding. Original hypotheses and the earlier insufficient-evidence pass
remain in episode history. Cumulative V8 conservative usage is $0.0332725 of $0.05
(not an invoice). No mappings/capabilities were promoted. This closes the bounded
hypothesis-checking checkpoint, not the question of exact component identity.

## Earlier checkpoints

Latest increment: ORYN owns a one-shot follow-up assessment of saved candidates.
It plans at most two targeted searches, stores retrieved excerpts plus local
selection decisions, then admits at most one image/reference comparison under the
same cumulative object cap. Support/conflict/insufficient-evidence outcomes are
separate assessment records: original hypotheses are never overwritten or promoted.
The real V8 follow-up completed in 0.622 seconds with **insufficient evidence**:
ten Wikipedia discovery results returned introductory excerpts, none qualified as
new component-specific context. The paid comparison was skipped; V8 usage remains
$0.0196625 at that point. This was a retrieval limitation, not a mechanical verdict or
successful reference-backed identification. The paid comparison path was then fixture-
tested only. The next explicitly authorized pass retrieved targeted technical sections and more
authoritative component references; preserve this unsuccessful attempt. No Quest
change, new generation, extra model charge or automatic retry occurred.

Latest increment: the user confirmed disabled API sharing with a Data controls
screenshot and authorized the bounded vision pilot. ORYN's application-owned
episode service now dispatches prepared images, records evidence/provenance/usage,
preserves unknowns and supports append-only reviews. The live three-piece V8 pilot
completed in 18.052 seconds: islands 001/002 received “Cylinder-bank upper cover”
**candidate** labels; island 003 stayed unknown. These are unverified hypotheses,
not established mechanical identities. No Quest build or runtime capability changed.
The conservative vision usage estimate was $0.01309; total with earlier text
research is $0.0196625 of the cumulative $0.05 object allowance. Actual invoice cost
is not asserted. Shared $2/day admission and no-retry behavior remain enforced.
The service runs explicitly requested episodes only, not all 200 V8 pieces or all
new generations. Next: reference-backed assessment of candidates, preserving the
original episode and rejected/corrected hypotheses. No new key was required.

Latest increment: local geometry evidence is now application-owned. The background
worker measured all 200 V8 pieces and all 39 drone pieces, producing four context
and four isolated diagnostic views for eight targets per asset. The first live
local preparations each took approximately 1.1 seconds, excluding later storage
compression/persistence. No generation, research, images-out or Quest actions were
triggered. Views are accessible through the existing object UI; all identities
remain unknown. Source-local AABB proximity is explicitly not mechanical adjacency.
At that earlier checkpoint, candidate mapping validation and immutable revision
storage were fixture-only; the subsequent live pilot is recorded above. No
semantic grouping or new runtime capability is enabled. The initial next step was to agree the
object-image data/cost policy, rasterize bounded views for the selected vision
provider, and test reviewable reference-backed candidates under spending admission.
See [geometry evidence contract](ORYN_WORKFLOW.md#local-geometry-evidence-checkpoint).

Latest increment: [persistent local investigation baseline](ORYN_WORKFLOW.md).
The user approved bounded Wikipedia/OpenAI research. The durable retrieval →
triage → synthesis worker is now wired into the live object-request service;
187 backend tests and mocked browser checks pass. A live V8 lookup saved five
references and selected three for synthesis. After the user saved the research
key in Keychain, ORYN automatically completed the investigation in approximately
12 seconds of synthesis-stage time. Conservative recorded usage estimate:
$0.0065725 (not an invoice), below the $0.05 ceiling. The application produced
source-linked object-family notes and left all mesh identities unknown.
The existing command service's memory-only connection is untouched. Next is
application-owned visual/structural evidence and reviewable candidate mappings,
not more generic V8 summaries. No verified component understanding is claimed.

ORYN now records acquisition routing and bounded geometry triage through a
provider-neutral `FastDecisionProvider`, with durable inputs/results, timing,
known-zero local cost and separate quality evaluation records. The saved V8 keeps
all 200 pieces and prioritizes eight for later investigation; no identities are
inferred. Reference retrieval and bounded text synthesis have passed one live
application-owned run. Visual component mapping is not implemented. Jev stays
experimental and uninstalled until the working
research baseline and labeled comparison exist. Existing command interpretation
does not substitute for that investigation worker.

Latest increment: [object ingestion v1](ORYN_INGESTION.md). Drone preparation now
reproduces 39 geometric targets through a checksum-bound manifest; V8 ingestion
preserves all 200 pieces without claiming component identities or flat explosion
support. Mapping provenance and explicit epistemic states are part of the record
contract. Semantic hierarchy/LOD and reference-backed mapping remain future work.
The prepared drone's live guided explode/reassemble test now passes (all 39 targets,
terminal result acknowledged inside Quest). See ORYN_XR_INSPECTION.md. Development
tests now communicate ready/testing/finished/blocked in-headset, not through chat.

Latest user decision supersedes the earlier per-request confirmation workflow:
**ask → generate → load → interact, no approvals.** Keep budget and validation
controls in the backend, not as confirmation dialogs. The default object-request
screen at port 8765 implements this with a fixed geometry profile, exact saved
prompt reuse, inspection, automatic delivery and actual import receipts. See
[generation contract](ORYN_GENERATION.md). No new live paid generation has been
performed for this change; next is a user-requested object and a hardware UX check.

The object-request box currently passes a description to the generation provider;
it is not yet a unified conversational router for actions, questions and generation.
The command lab remains a diagnostic tool with its earlier explicit gates.
Do not impose those lab gates on the default object-request experience.

## Earlier diagnostic pilot (remaining coverage, not default UX)

Keep the existing runtime, provider boundary, action confirmation and cost gates.
Use the command console rather than building another UI or a new agent framework.
Start with three individual requests, not an autonomous multi-call loop:

1. With a geometric part selected, "Show only this piece." Expected: an isolate
   proposal bound to that exact part. Nothing moves until action confirmation.
2. "Put everything back together." Expected: reassemble proposal and, after
   confirmation, an executed receipt plus all 39 parts restored.
3. "What does this part do?" Expected: no invented function, components or
   relationships. The current contract may decline this as unsupported. It must
   distinguish a user annotation from verified knowledge and propose no action.

For each request record interpretation latency, expected vs returned intent,
quoted maximum, ledger settlement/reservation status, and confirmed execution
where applicable. A valid JSON response is not proof that the interpretation is
correct; evaluate both contract and meaning. Preserve failed results, do not
automatically retry, and do not claim a three-case pilot establishes broad quality.

Before external requests: confirm the chosen provider/profile is configured,
review its current pricing/availability, obtain permission to send the text for
counting, then obtain approval of the exact quoted generation maximum. Each
runtime action remains separately confirmed. Existing generation credentials do
not imply a language-provider credential is configured. Never print credentials
or commit them. Do not bypass stale-headset or spending gates to run the pilot.

References: [command contract](ORYN_COMMANDS.md),
[spending controls](ORYN_SPENDING.md),
[OpenAI structured-output contract](https://developers.openai.com/api/docs/guides/structured-outputs).

## Next, after the automatic object-request check

- Unify the object-request and interaction paths behind a conversational router,
  preserving the no-approval UX and backend spending/validation boundaries.
- Extend evidence-backed knowledge and explanations beyond user labels.
- Add spoken input through the same validated intent/action boundary, not a
  separate unrestricted voice agent. Long-term input: gaze, hands and voice,
  with controllers as a fallback.

## Recorded storage direction: cloud-backed library, bounded device caches

User decision: generated assets should ultimately live in a cloud library rather
than accumulating indefinitely on the development Mac or headset. This is a
future architecture requirement, **not an implemented storage migration**.

- Cloud object storage is the durable home for originals and derived variants;
  persistent metadata/knowledge links them by stable asset IDs and checksums.
- Mac/Quest copies become bounded, evictable working caches. Active assets remain
  pinned while in use. Cache eviction must not delete the durable cloud asset or
  its knowledge. Preserve local-only assets until a verified upload exists.
- Preserve ownership/access control, provenance, versioning and reference integrity
  across geometry and knowledge. Keep provider keys server-side and authorize
  asset access through the ORYN backend.
- Storage, downloads and retention need their own quotas and cost controls;
  generation-token budgets do not cover them. Provider, region, retention policy,
  cache sizes and rollout remain undecided.

Do not provision a cloud account, upload existing assets, delete local files,
install new SDKs or rewrite storage during this UX milestone. No cloud
provider has been selected or authorized for deployment. Preserve the working
prototype while keeping local paths out of future public asset contracts.

## Previous quote-gate checkpoint (resolved)

Live exact token counting succeeded for "Put everything back together": 2,979
input tokens and a conservative maximum of $0.0176875 at the reviewed routine
profile. The approved interpretation was blocked before provider dispatch because
the original quote was bound to transient live context. No paid interpretation
completed and no action was applied.

The user approved separating interpretation from execution. Quotes now freeze the
counted facts, while runtime actions revalidate meaningful context and readiness
immediately before dispatch. See [the updated command contract](ORYN_COMMANDS.md).
The subsequent live reassembly test passed, as recorded above. These exact-quote
gates remain available in the developer command lab; they are not the approved
user experience for object generation.
