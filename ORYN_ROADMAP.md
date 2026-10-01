# ORYN working roadmap

Last checkpoint: 2026-09-30. This file records the agreed direction so new ideas
do not silently replace the current milestone.

## Product goal

Request an object in natural language, obtain or generate geometry, interact with
it spatially, and investigate it using persistent, evidence-backed knowledge.
Geometry generation and object understanding are separate responsibilities.
Generated shapes and user labels must not become verified mechanical facts.

Long-term, the object may be a complete intelligent package with GLB carrying its
geometry. The [existing contract mapping and deferred note](ORYN_COMPLETE_OBJECT.md#relationship-to-the-research-contract)
cover the shared concepts. A new format, schema rewrite, packaging system and `.oryn`
implementation are explicitly outside the next milestone.

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

## Current milestone: native-object generation experiment

Immediate question: **Can this pipeline consistently generate a visually coherent
object with useful separate components?** Current failed trials remain stopped;
assessing the next approach serves this same question.

User priority: visual object quality, meaningful components and behavior on the
same generated object. The core generative capability is part of the invention;
a permanent fixed-parts configurator is not the destination. General answering,
voice and question-specific answer patches are paused. Existing answer fixtures
are not evidence that autonomous answering works.

The [native-object experiment](Research/native_objects/README.md) now provides an
isolated output representation, partial evaluator, actual Unity mesh/motion control
export, source-preserving saved-geometry comparison, visual inspector and prepared
PartCrafter inference adapter. Offline checks cover the research contract; Unity export and browser
controls pass. Authored motion agrees with sampled geometry; the saved generated
model remains missing semantics, hierarchy and motion. Neither passes the complete
native generation goal. Appearance, attachment fit and clearance remain unassessed.

The first PartCrafter GPU run completed: 13 meshes, 195,708 triangles, 204.461
seconds, no manual repairs. Structure passes; desktop visual quality falls short,
with floating fragments and malformed major shapes. Semantics, hierarchy and
motion remain unknown. Estimated rental cost was $0.077; the pod was terminated.
See the [measured result](Research/native_objects/results/partcrafter-run-001.json).

The [predeclared framing comparison](Research/native_objects/FRAMING_COMPARISON.md)
is complete; [results and scorecard](Research/native_objects/FRAMING_RESULT.md) are
recorded. B improves recognizability, but scores only 2/6 visual and 3/8 component
usefulness against A's 1/6 and 2/8. The material-improvement gate fails. B has
1,090,246 triangles; part_09 exceeds the unchanged static import limit. Offline
inspection preserved that failure and all original meshes. Quest was not attempted.
Estimated A+B rental cost is $0.1541; both pods were terminated, with no remaining
pods or network volumes. Billing records have not settled.

Stop paid trials of this configuration; do not automatically buy seeds 1/2 or
promote B. The bounded [planning experiment 001](Research/native_objects/PLANNING_RESULT.md)
completed four diverse live requests with one shared model policy and no object-specific
recipes. All four met their predeclared planning criteria, including refusing to invent
exact-product internals without evidence. Estimated usage was $0.020945 against a
$0.20 ceiling. This tests request interpretation and evidence needs in four cases;
it does not prove retrieval, geometry, repeatability or generalization.
The subsequent [Cube geometry comparison](Research/native_objects/CUBE_RESULT.md)
is also complete. The same bridge ran unchanged plans for a drone and a creative
lamp; both assembled forms were coherent but component fidelity failed (7/10 and
6/10, with every dimension needing 2/2). The speaker's nine groups exceeded the
pinned eight-slot pipeline; exact-product reconstruction stayed evidence-blocked.
Zero output repairs or inference retries. Rental estimate $0.4782; independent
cleanup confirmed zero pods and network volumes. No Quest import was attempted.

Stop both tested configurations without buying more seeds. The bounded
[construction-guidance preflight](Research/native_objects/STRUCTURE_PREFLIGHT.md)
checked four candidates and reproduced loss of a small part label in OmniPart's
input downsampling, without model inference or GPU spend. That audit established no
complete external-generator input path covering all unchanged requests. It identified
the gap between existing role-group proposals and spatial construction. The following
procedural experiment addresses that gap. The
predeclared gates require useful components, identity preserved through refinement,
and measured cold/resident-model latency; 30 seconds to useful assembly and 120 to
refinement are research targets, not demonstrated capabilities. A good exterior or
part label is insufficient. These few trials do not establish every model's ceiling
or justify training. Product changes, answering and motion expansion remain paused.

The [procedural construction experiment](Research/native_objects/CONSTRUCTION_RESULT.md)
now connects one application-owned policy to a deterministic geometry builder. Four
requests produced 19/11/5/6 separate instances with no manual numerical rescue. All
declared spatial measurements passed, but proxy geometry and missing interfaces
failed the visual gate. The unfamiliar sharpener's absent guide opening and disconnected
drive/cutter fail semantic coverage. Cost estimate $0.19322; file-ready 30.82–55.04
seconds with role plans replayed. No GPU rental or Quest import. Preserve this partial
structural-control evidence; the next unresolved decision concerns general interface
geometry and omitted essential connections, not another successful-generator claim.

The subsequent [solid construction and feedback experiment](Research/native_objects/SOLID_RESULT.md)
added general boolean geometry and an application-owned review/correction loop.
The lamp and sharpener each corrected a measured geometric failure automatically,
but neither passed visual/semantic assembly review. Drone and speaker returned no
retained response around the sender's 120-second limit; their geometry is unassessed,
not failed. Completed usage estimate $0.4415 plus $0.25535 held for uncertain calls.
No GPU or Quest run. This frozen batch is stopped; response diagnostics and interface
observability precede further paid comparisons. No finished generator is established.

The [executable-connection experiment](Research/native_objects/CONNECTION_RESULT.md)
now derives placement from geometry-backed faces/axes and locks requirements across
repair. The drone corrected four disconnected motor solids and passed declared
checks. The lamp passed its checks while omitting the requested seed-inside-leaf
relationship, so request coverage fails. Speaker and sharpener exhausted their
response-token allowances; geometry is unassessed. Estimated API cost $0.578555.
A post-run precision fix was audited against unchanged saved geometry; verdicts
were unchanged. Requirement coverage and response limits remain unresolved. No
unfamiliar-case, Quest or finished-generator success is claimed.

The [request-to-requirements experiment](Research/native_objects/REQUIREMENTS_RESULT.md)
adds frozen source requirements and deterministic typed bindings before unchanged
geometry execution. All four plans account for their extracted IDs. The lamp's
inside/suspended/glowing intent survives; unsupported suspension/emission blocks
construction. Drone and automatically repaired speaker pass declared checks;
sharpener fails two connection checks and its repair cannot be reserved under the
remaining budget. All responses complete at the unchanged construction token limit.
Estimated cost $0.3953575. A general uppercase-ID validator defect was corrected by
revalidating the unchanged saved extraction, with the initial failure preserved.
Coverage does not prove correct extraction: conceptual appearance, implied structure
and engineering function still need better distinctions. Keep geometry frozen;
no polished-object or generalization success is claimed.

The [meaning experiment](Research/native_objects/MEANING_RESULT.md) exposed
fabricated references and ambiguous capability output. The follow-up
[006–007 confirmation](Research/native_objects/MEANING_CONFIRMATION_RESULT.md)
uses application-assigned source/component IDs and explicit capability meanings.
All seven frozen cases produce complete valid inventories meeting the original
limited assertions. The lamp's seed remains suspended inside; static controls,
motion and verified claims remain distinct. The corrected inventory enters the
existing planning gate, with unchanged live lamp/drone outputs blocking unsupported
work before planning. 196 targeted test executions pass; geometry remains unchanged.

That confirmation did not prove lossless interpretation or general object generation.
Spatial intent survived but lacked checkable adapters, and static-pose representation
varied between requests. This motivated the spatial bridge measured below, while
preserving unsupported requirements.
Additional API estimate $0.152625; zero new uncertain reservations. The user tripled
the shared daily API cap to $6 on 2026-10-01; the $5 aggregate research cap remains.

The [spatial bridge experiment](Research/native_objects/SPATIAL_RESULT.md) now runs
registered spatial checks on solved geometry. The static hanging-sphere concept is
coherent with four selectable/separable parts and passing checks. The drone passes
its pairwise spatial rules but omits shared orientation across its motors/propellers;
one ESC symmetry also fails. The speaker repairs missing connection bindings and
then fails housing connectivity. Lamp emission and sharpener feed/collection paths
remain unsupported. No geometry executor change or production promotion occurred.

Next: require explicit arrangement/axis relationships across repeated component
groups before construction, without an object-specific recipe or another symmetry-only
repair. Additional API estimate $0.46642. A lossless context change fixes the blocked
repair quote without increasing limits or dispatching another generation. 248 targeted
test executions and seven browser checks pass. This is a narrow simple-concept success,
not a general-object or visual-quality breakthrough.

Generation research is the active track. The product remains stable; answering,
voice and motion-inference expansion are paused. Research output does not enter
production automatically. The existing $5 research ceiling includes the prior run.

Local work now separates object structure/quality, application-owned behavioral
judgment, and optional validated animation. Missing animation does not fail object
structure and does not imply a deliberate decision to stay static. Behavioral
judgment has an application-side model interface and candidate validator in
`Orchestrator/behavior_decision.py`. It binds proposals to the exact object, request
and selection; rejects invented IDs/stale results; and never enables execution.
Fifteen offline tests use scripted responses, not demonstrated model judgment.
No live adapter or production route is connected; reports keep judgment unassessed. This remains
preparation for later behavioral measurement, not demonstrated intelligent judgment.
Do not replace failed generated output with a manually assembled demo. Record all
supplied structure, failed outputs and manual repairs. Use the observed failures
to choose subsequent articulation work or model adaptation.

## Wrist controls (2026-09-29)

The latest user correction requests faster opening from a palm-up fist with the
thumb extended, and separate controls on the two arms. Version 1.14.2 (20) opens
directly after an 80 ms pose hold; there is no launcher pinch or open-palm reveal.
Bone geometry checks all four curled fingers and a straight thumb extending away
from the index side. Missing bones, low finger confidence and non-finite inputs
reject the pose. Both legacy and OpenXR skeleton joint mappings are supported.

Left wrist opens Inspect actions; its Tools center also exposes Objects and
Details. Right wrist opens Motion actions. The right fan mirrors inward without
mirroring text. The opposite hand/controller selects each menu. Only one fan is
shown at a time so both hands remain usable. Controllers use left Y / right B
for their respective menus. Following smoothing is reduced from 35 ms to 15 ms.

After opening, fingers may relax while the palm stays up. Turning the palm down,
losing focus/tracking or grabbing with either hand closes the menu. A held pose
cannot reopen it after dismissal or manipulation; release and form a fresh pose.
The broad 10 cm proximity block was removed: merely being near a figure must not
prevent this deliberate pose from opening. Active grabs and prayer-spread still
take precedence. Existing press latches prevent an opening gesture or held trigger
from selecting a newly exposed action.

The curved fan, short labels and thin wrist tether retain the user's visual
references. Controls are 9–19 cm from the wrist anchor. Local tests cover both
hand geometries, several hand sizes, pose timing, release/rearm and mirrored
selection. Synthetic tracking tests and editor renders cannot establish real
headset detection reliability; that acceptance remains open. General answering remains paused. The completed paid research runs and comparison are
tracked in the current milestone above.

## Earlier milestone: Complete Object Experience / MVP 1

The user approved implementation with ORYN owning its own brain; Codex must not
operate the product as a runtime puppeteer. First increment: the authored drone
through an application-owned typed interpreter, stable object/component identity,
grounded authored explanations, follow-up context and validated automatic commands.
See [Complete Object v1](ORYN_COMPLETE_OBJECT.md). Voice, visual polish and full
uncoached Quest acceptance remain required before calling MVP 1 complete.

Latest continuation: the typed integration is committed. ORYN now owns in-headset
conversation feedback and cancellation before dispatch, with post-action reference
receipts and late-response protection. 264 offline Python tests and the Unity build
gates pass. The 1.13.1/code 17 update is installed and launched; user visual
acceptance remains open. One explicitly approved live read-only interpretation
passed against the Unity-exported authored fixture: “What does this motor do?”
resolved to the selected motor and ORYN's authored explanation in 4.812 seconds,
with a conservative usage estimate of $0.00621. No Quest action or retry occurred.
Headset integration acceptance, voice, full interruption and visual polish remain
open. See the Complete Object checkpoint for exact verification scope. The first headset request received an executed drone
receipt, but the user's basic flight question exposed an overly restrictive
interpreter and missing general propulsion explanation. That route now has a
separately sourced explanation without promoting mesh evidence; 268 offline tests
and browser checks pass. Live retest and user visual acceptance remain open.

### Completed mechanical foundation

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
is not asserted. Shared $6/day admission (user increased it on 2026-10-01) and no-retry behavior remain enforced.
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
