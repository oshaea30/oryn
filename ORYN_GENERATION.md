# Oryn: geometry → inspection → optional texture → Quest

## Priority and status

The user confirmed that runtime asset loading, manipulation and resizing work. They
explicitly reprioritized **asset generation on command** and now wants a structural
drone benchmark with provider-independent semantics. Leave accepted controls alone.
This increment establishes staged generation and structural inspection; it does not
implement explode/reassemble, semantic reasoning, voice, or independent part grabs.

**Implemented:** localhost Mac console, Meshy adapter, explicit paid approval, job
progress/history, saved GLB variants, structural reports, explicit USB delivery,
checksum-verified Quest imports, and headset receipts. Generation stops at inspection.
Only the explicitly labeled test-avocado delivery button combines fixture inspection
and transfer. Existing geometry can be delivered without regenerating it.

**First live experiment completed:** one Structure Test drone geometry task, explicitly
authorized by the user. The supplied credential was loaded into local service memory
without printing it or copying it into source/configuration. API balance changed from
1,100 to 1,095 credits; no texture task or paid retry was submitted. Generated GLB:
192,716 bytes, 10,491 triangles, 5,509 vertices, no textures/materials, static preflight
PASS. It contains **one mesh node**, not the distinct component objects we hoped for.
This proves live generation/download/inspection, not multipart semantics. Mock
provider tests alone do not establish generated geometry quality or compatibility.
The test avocado is an existing CC0 fixture, never presented as AI-generated output.

## Start / use

Keep one authorized Quest connected over the existing USB cable; open Oryn in the
headset. On the Mac, from `/Users/oshaealexis/Developer/Oryn/Unity-StarterSamples`:

```sh
python3 Orchestrator/app.py
```

Open **http://127.0.0.1:8765**. The service is bound to loopback, not the LAN. No Python
package installation is needed (tested with Python 3.14.3; standard library only).

1. Finish the pending avocado receipt check before the first paid experiment. If no
   test is pending, click **Send test avocado — no generation**. Leave a clear nearby
   spawn slot. The existing startup cube/avocado remain; avoid sending duplicate copies.
2. Rotate any shared API key in your Meshy developer account.
   Paste the key into the **local console**, not this chat or the repository. It stays
   in service memory; restarting clears it. Optional advanced setup uses the
   `ORYN_MESHY_API_KEY` environment variable. Do not put a secret directly in shell history.
3. Click **Check API balance — no generation**. It makes one authenticated GET, not a
   generation request. Do not assume a quoted subscription allocation is available.
4. Keep **Structure Test** selected for the prefilled quadcopter prompt. Approve its
   estimated **5 credits**, then click **Generate geometry**.
5. Inspect mesh-node count, unique meshes, scene hierarchy, triangle count, materials,
   textures, bytes and static preflight. Nothing is automatically sent to Quest.
6. Click **Send geometry to Quest** only after inspecting the result. Once tracking,
   focus and a spawn slot are available, the Quest imports it and returns a receipt.
7. For a later **Quality Test**, approve 20 credits for geometry. Optional 2K texture
   is a separately approved 10-credit operation. Geometry is kept unchanged, even if
   texturing fails. Choose which saved variant to deliver.

Profiles (published estimates verified 2026-09-26; check current pricing before use):

| ORYN profile | Provider geometry | Target | Geometry | Optional texture |
| --- | --- | --- | --- | --- |
| Structure Test (default) | `meshy-t2`, `smart-topology` | 10,000 triangles, GLB | 5 credits | Disabled pending documented T2 refine compatibility |
| Quality Test | `meshy-7.1`, `standard`, `should_remesh: true` | 10,000 triangles, GLB | 20 credits | 10 credits, 2K, no extra PBR maps |

T2 generates directly at the requested face count; no separate remesh request is
made. Target count is not an output guarantee. The refine docs do not list T2 as a
supported model, so we do not silently switch texture models or charge for an
undocumented combination. The 15-credit T2 textured entry in the pricing table is
for **Image to 3D**, not proof that Text to 3D refine accepts a T2 preview.

The developer-platform docs describe plan-credit usage; the pricing page describes
prepaid API credits. The read-only balance endpoint reports what this key can see.
No account balance or subscription entitlement was verified during implementation.

- [Meshy Text to 3D API](https://docs.meshy.ai/en/api/text-to-3d)
- [Meshy authentication / account setup](https://docs.meshy.ai/en/api/authentication)
- [Meshy API pricing](https://docs.meshy.ai/en/api/pricing)
- [Meshy balance endpoint](https://docs.meshy.ai/en/api/balance)
- [Meshy developer platform](https://docs.meshy.ai/en/api/developer-platform)

## Boundaries / replaceability

- `Orchestrator/providers.py`: `GenerationProvider` protocol and first adapter,
  `MeshyProvider`. Geometry, texture, and balance are separate operations. Model IDs
  and payload mappings stay here, outside the runtime. API credentials never leave
  the Mac except for authenticated HTTPS
  requests to Meshy. CDN download requests never carry the API key. Unexpected asset
  domains or redirects are rejected.
- `Orchestrator/app.py`: local console routes, approval/input validation, single active
  job, idempotency IDs, job records and model cache. No reasoning model or intent router
  is needed just to forward an object prompt.
- `Orchestrator/asset_inspection.py`: read-only bounded GLB metadata inspection.
  The original bytes and node hierarchy are never flattened, renamed, or modified.
- `Orchestrator/transport.py`: replaceable USB delivery using ADB. No wireless debugging,
  LAN listener, Android network permission change, or backend URL in the headset.
- `OrynGenerationInbox`: bounded manifest/checksum validation; calls existing model
  import; writes an acknowledgement only AFTER successful workspace adoption.
- `OrynRuntimeModel` / workspace: existing GLB rendering and accepted object controls.

Geometry is saved in `.oryn-generation/<job-id>/model.glb`; optional texture in
`textured.glb`, each with a sibling `.inspection.json` report. The job record contains
both reports and explicit credit approvals. Older cached jobs are inspected locally
on service startup, without generating or delivering anything.
This ignored folder also contains job/task IDs and prompts, but no API keys or signed
provider URLs. Creation defaults to private filesystem permissions. At most 20 local
jobs are accepted; at least 512 MB free space is required before starting a new job.
No files are automatically deleted to make room.

Quest receives `<delivery-id>.glb`, then an atomic `<delivery-id>.json` manifest in
`Android/data/com.oryn.milestoneone/files/GenerationInbox`. It replies with a `.ack`
receipt. A delivered model can be sent again without a generation charge; each explicit
resend creates a fresh delivery ID and may create another visible copy. Receipts prevent
the same manifest from being imported repeatedly. Workspace layouts remain session-only.

## Failure / spending behavior

- No paid POST retries: a timeout can mean the provider created and billed a task.
  Inspect saved task IDs and the provider dashboard before submitting again.
- A request UUID is persisted before contacting the provider. Repeating the same
  request returns its existing job. The browser retains only the pending geometry
  request UUID across reloads, never credentials or prompts. Changing the profile
  clears its approval. The API also verifies the approved estimate against the profile.
- At most one texture attempt per job, including after failure/restart. A repeat of
  the same texture request UUID returns the saved job; a new texture UUID is rejected
  if any attempt already exists. Recovery must inspect provider history first.
- Restarting the Mac service never silently restarts paid jobs. Interrupted jobs are
  marked and task IDs retained. Automatic resume of provider generation is not built.
- Provider polling is bounded to 20 minutes per stage. Poll failures stop locally; an
  already-created provider task may continue. Stopping this service does NOT cancel or
  refund provider work. No destructive provider delete/cancel API is used.
- If USB delivery fails, the generated GLB stays on the Mac. **Send saved model to Quest**
  retries only delivery. No model exists for a job whose generation/download failed;
  its provider task IDs support manual recovery.
- “Waiting for headset” is not success: wear/open Oryn, allow tracking, and move an
  existing object aside if the nearby slots are full. Receipt polling continues while
  the Mac service is running.
- Generated assets must still pass existing Quest import limits (self-contained GLB,
  up to 16 MB, static meshes, at most 128 renderers / 200,000 counted vertices). A
  provider request targeting low polygon count is not a guarantee. Rejected results
  may already have incurred generation charges.
- The receiver uses a bounding box for imported-model interaction, unchanged from 1.5.
  Generated meshes are not automatically semantic objects with physical interiors.

## What inspection does and does not prove

The report counts the default scene (first scene if none is selected). Distinct mesh
nodes are counted separately from unique mesh definitions and primitives. Reusing one
mesh in two nodes counts as two objects, one unique mesh, and twice the scene triangles.
Multiple primitives in a node are not reported as independent objects. Node indices
and parent indices preserve identity when names are missing or duplicated.

Checks cover header/chunks, resource-table bounds, active-scene graph cycles and
duplicate parents, buffer/view/accessor ranges, triangle topology, self-contained
resources and conservative renderer/vertex limits. URI resources, unsupported required
extensions, compression, skinning and morphing block delivery. Vertex count is a
conservative upper bound because shared primitive attributes can be counted twice.

**PASS means static preflight only**, not full glTF validation or a Quest certification.
Binary geometry validity, finite/nonempty transformed bounds, GPU texture memory,
material support, visual quality and gestures still require glTFast/headset validation.
The inspector never downloads referenced resources. Sending saved models reruns
inspection and checks that their checksum matches the cached report.

## Next benchmark: authored versus generated drone

### Offline island recovery (first generated drone)

Although the provider delivered one mesh node, binary connectivity inspection found
**39 vertex-index-connected triangle islands**. An exact-position seam diagnostic
merges two of these into one, yielding **38**. Neither count is a semantic part count:
point contact and duplicated seam vertices do not establish mechanical identity.
No tolerance welding, cuts, or geometry repair were performed.

`Orchestrator/mesh_islands.py` exports a new multi-object GLB, preserving the original
transform and every triangle's coordinates, winding and multiplicity. It is purposely
restricted to the first drone's static, single-node, single-primitive, indexed,
uncompressed, POSITION-only layout. Unsupported normals, UVs, textures, skinning,
extensions or scene layouts are refused rather than silently discarded.

Output directory:
`.oryn-generation/194f107aee2550dd9369453ad3fe6bb8/island-analysis/`

- `drone-islands.glb`: 39 mesh objects under the original-transform parent, 10,491
  triangles, 5,509 vertices, 216,912 bytes; static preflight PASS.
- `islands.json`: stable source-checksum-scoped IDs, source face indices, local bounds,
  counts and explicit unassigned semantic labels. Includes raw and exact-weld counts.
- `index.html`: offline diagnostic preview; rotate, highlight, isolate with auto-fit,
  and explode/reassemble locally. No external libraries, provider calls or credentials.
- Output SHA-256: `878b7944ee5bc752e8367cbf060b991f747888ad28de98994c7bd8c2120b2553`.
- Original SHA-256 remains `ac04c5da67eaa008d349ffc9cf2a9c98db0db28731d1bb5ba2c1726b6c224559`.

Visual inspection suggests rotor blades and motor-housing pieces are distinct islands.
The central body and arms remain joined in the largest island. These observations are
provisional, not automatic semantic classification or proof of realistic engineering.
The source has NO individually labeled battery/motor graph yet.

The preview runs locally at `http://127.0.0.1:8766/` while its static server is running.
It is separate from the generation console at port 8765, which was not restarted
(its memory-only key remains in that service). The Quest app and controls were NOT
modified, and this derivative was NOT installed as a new independently grabbable asset.
Next runtime work must explicitly support part selection/manipulation and assembly
state; merely exporting separate nodes does not provide that behavior.

**Subsequent runtime milestone:** ORYN 1.7 now implements the part interaction,
explode/isolate and reassembly controls described in [ORYN_ASSEMBLIES.md](ORYN_ASSEMBLIES.md).
The paragraph above records the earlier offline-inspection checkpoint. Runtime editor
tests pass and the update is installed; the physical interaction walkthrough still
needs the user's hardware feedback. No further generation credits were used.

Reproduce into a NEW output directory (existing directories are never overwritten):

```sh
python3 Orchestrator/mesh_islands.py path/to/model.glb path/to/new-output-directory
```

Verification: 46 Python tests pass, including new triangle roundtrip, seam ambiguity,
no tolerance welding, transform preservation, deterministic IDs/provenance, invalid
indices, finite positions, attribute-loss rejection, duplicate/degenerate face retention,
and interleaved/16-bit index inputs. Actual drone triangle-coordinate multisets and
source transforms were compared exactly before/after export. Browser checks passed
for rendered geometry, 39 options, isolation, reset, mobile overflow and no JS errors;
assembled, exploded and isolated views were visually inspected. No paid API calls.

No authored drone asset was found in the active repository during this increment.
Before claiming semantic parity, build/import a known multipart drone and author its
component identities and relationships. Prove isolate/explode/remove/reassemble and
explanations on that controlled object, then ingest generated candidate parts into the
same provider-neutral object graph. Mesh names alone are not trustworthy semantics.

Auto Split is a separate possible later experiment, not an automatic step or charge.
Its current docs exclude T2, accept Meshy 6/7-family models, and describe printable
parts rather than semantic identity. It can rebuild cut geometry and removes textures.
[Auto Split reference](https://docs.meshy.ai/en/api/auto-split).

## Verification record

- First paid geometry job: `194f107aee2550dd9369453ad3fe6bb8`.
  Provider preview task: `01a0e0f0-5ee2-7786-baee-0442cbf00ca1`.
  GLB SHA-256: `ac04c5da67eaa008d349ffc9cf2a9c98db0db28731d1bb5ba2c1726b6c224559`.
  Structure Test, 5 credits observed balance difference; original GLB preserved.
  Only node: `mesh_node`, mesh 0. Separate-component benchmark NOT met.
- User confirmed the avocado can be grabbed, moved, rotated and resized, and its
  headset receipt was received. User still considers pinch resizing a regression
  versus the first controls; functional confirmation is not acceptance of its feel.

- 36 Python tests passed with mocked provider calls, covering cost/key gates, explicit
  demo labeling, idempotency, failure persistence, restart behavior, no paid timeout
  retries, profile payloads, optional texture isolation, balance GET validation,
  changed-file rejection, scene hierarchy/instances, malformed GLB rejection,
  CDN credential isolation, URL restrictions, manifest-last transfer, device selection,
  Host/Origin/CSRF checks and key redaction.
- Avocado local inspection: 8,110,040 bytes, 1 mesh object / 1 unique mesh / 1 primitive,
  682 triangles, 406 vertices, 1 material, 3 textures. Static preflight PASS. This is
  fixture evidence, not evidence of a generated drone or separate-part manipulation.
- This increment changes only the Mac service/UI; the existing 1.6 receiver is retained.
- Previously: 365 Unity checks passed (284 workspace, 66 legacy, 15 runtime/manifest checks).
- The local console was rendered and visually inspected in an isolated headless Chrome
  profile. Browser preview process was then stopped; the console service remains running.
- Android 1.6 / code 7 built in 53.6 seconds, Unity exit 0, APK signature verified,
  installed successfully and launched with `Status: ok`.
- APK SHA-256: `66784a2bd75b28d8346d45350f020a2182175c39cb0d1cd78156a10d25596004`.
- Build log: `/private/tmp/oryn-generation-build.log`.
- Test-only delivery job: `82acb78911544a259255be8ce52937a0`;
  delivery: `0d5a75f2206f434e86619f29328b06c7`. Transfer completed; initially waiting for
  headset tracking. Receipt outcome is recorded separately after the hardware check.

Repeat automated checks:

```sh
python3 -m unittest discover -s Orchestrator -v
```

Use the existing `OrynRuntimeModelTests.ValidateAndBuild` Unity entry point for the APK.
Neither test suite sends live generation requests.
