# ORYN 1.9 — persistent part annotations

**Current recovery update: 1.9.2 / code 12.** BRING MODEL replaces the legacy avocado
loader, recovers an existing assembly without touch, and preserves component records.
Objects spawn/recover at 45 cm forward, 8 cm below the eyes. Startup no longer creates
a cube or imports the old avocado. Successful non-demo generation deliveries also
update the checksum-verified startup cache, even before annotations are saved.
The most recently remembered model (delivery or annotation) is restored on restart.
This remains eye-relative placement, not detection/collision with the user's desk.

1.9.2 verification: **1,030 Unity checks** passed, including 37 new recovery checks
for standing/seated reach, steep head pitch, recovery without prior selection, an
avocado/primitive not hiding the assembly, reassembly, original geometry mapping,
and repeated recovery without duplication. Python: **46 passed**. Build succeeded
in 38.47 seconds with Unity exit 0; signature verified and APK installed/launched.
Log: `/private/tmp/oryn-recovery-build.log`.
APK SHA-256: `8938418f9cd4636d7500e4c079c9e7e9ad35b37d366b25dd3758b4629ea1d02f`.
Existing drone delivery: `94db71eeb2af48fcb4d3aa46a86b63a4`; no paid API calls.
Receipt state: `.oryn-generation/194f107aee2550dd9369453ad3fe6bb8/island-analysis/quest-recovery-delivery-v1.9.2.json`.
Reach relative to actual furniture still needs the user's physical headset test.

Menu usability update **1.9.1 / code 11** raises the panel, adds controller pointing
with trigger/A/X, and reserves B/Y for menu-only recentering. Record format, label
history, prayer spread and object manipulation are unchanged. See ORYN_WORKSPACE.md.

1.9.1 verification: **993 Unity checks** passed, including 254 new menu checks for
seated/standing heights, extreme head pitches, tracking-origin offsets, ray bounds,
nearest targets, hidden/back-facing panels, and fresh-press gating. Python: 46 passed.
Build succeeded in 46.17 seconds, Unity exit 0; signed APK installed with app data
retained and launched on Quest. Log: `/private/tmp/oryn-menu-build.log`.
APK SHA-256: `a8b2d6e433b8ed9fa8820e05dcdbf2531775fa8e3c6517a662ee6285048f210d`.
No saved-model pointer existed before this install, so the existing drone was resent
as delivery `15e2ef6d731c422a82e6f41f169999ef` (no regeneration). Receipt state:
`.oryn-generation/194f107aee2550dd9369453ad3fe6bb8/island-analysis/quest-menu-delivery-v1.9.1.json`.
Physical menu comfort and controller pointing still require the user's headset check.

This milestone adds records and a headset inspector. It does not identify components
automatically, introduce an AI provider, or claim verified engineering knowledge.
The accepted 1.8 prayer gesture and existing manipulation/resize math are unchanged.

## Try it

1. Use prayer-to-spread on the 39-part drone, then grab/release a piece to select it.
2. The PART KNOWLEDGE panel shows a stable ID, saved label, annotation revision,
   verification status, and source. It explicitly reports evidence/connections unknown.
3. Use `< LABEL` / `LABEL >` to choose a draft. These are a fixed vocabulary of user
   choices, not model predictions. Use **SAVE** to apply. Moving to another piece
   discards any unsaved draft. SAVE is disabled unless the label actually changes.
4. To retract an identification, choose **Unidentified (clear)** and save. Older
   annotations remain in the history, including their timestamps.
5. After saving, restart ORYN. It opens a checksum-verified local copy of the last
   annotated assembly instead of the old startup avocado. Explode and select the
   same piece: the saved record should be restored. Other unacknowledged USB deliveries
   can still load through the existing inbox.

For this version the label picker contains Chassis, Battery, Arm, Motor, Propeller,
Flight controller, Housing, Fastener, Other, and Unidentified. Custom text entry,
evidence editing, relationship authoring, and verified-identity workflows come later.
Do not label a piece just because a category is offered. The generated drone's body
and arms are fused, and several separate pieces have not been identified.

## Identity and storage

- Every imported assembly part receives its original renderer hierarchy address
  before any interaction wrappers reparent geometry. Sibling indices distinguish
  duplicate mesh names. The mapping algorithm is explicitly versioned.
- The stable part ID is SHA-256 of the exact GLB checksum, mapping version, and
  geometry address. Reimporting the identical file under another delivery filename
  restores the identity. A changed GLB gets a new identity; label migration requires
  a future explicit mapping process. IDs identify asset components, not scene instances.
- Selecting a part materializes its initially-unidentified record. Saving adds an
  append-only annotation event with revision, label, `local_user` source, `unverified`
  status, and UTC timestamp. A user annotation is not a verified identity or measured
  confidence score. No relationship or operational consequence is inferred from it.
- Data lives under `Application.persistentDataPath/Knowledge` on Quest:
  `Records/<asset-sha>/<part-id>.json`, `Models/<asset-sha>.glb`, and `last-model.txt`.
- JSON publishes with a same-directory temporary file, flush, and atomic replacement.
  Previous records are retained as `.bak`; incomplete temporary files are never read.
  Malformed records, unsupported schemas, changed bindings, stale revisions, and
  unsupported verification claims fail closed. They are not silently reset or replaced.
- The record store supports single-process local writes; it is not a multi-user database.
  Maximum 1,000 annotation events per part and 1 MiB per record. Model files retain the
  existing 16 MiB cap. Cached models are not automatically garbage-collected yet.
- The last annotated model is restored, not the entire scene layout. Positions,
  hand holds, selection, spread, and moved parts remain session-only.
- App updates retain records; uninstalling/clearing app data can remove them. USB
  backup/export and cross-device synchronization are future work.

## Architecture decision

ORYN owns object/evidence records, runtime state, and action validation. Cognitive
providers will be replaceable; neither OpenAI nor Gemini is selected as the winner.
After records/inspector, add a small provider interface and identical-task comparison,
then voice and blinded headset evaluation. No Jev, model router, paid generation,
fine-tuning, external data transfer, or AI API credentials are needed for this milestone.

## Verification

`OrynKnowledgeTests` exercises fresh records, save/reload, correction/retraction history,
stale writes, invalid labels, path traversal, corrupt/schema-mismatched files, backup
retention, model-cache verification, and actual GLB reimport under a different filename.
Inspector checks exercise draft isolation, explicit save, clear, and selection changes.
The existing assembly, prayer, workspace, legacy, and runtime tests also run.

The build renders both empty and populated inspector previews. Physical readability,
button reach, and the complete headset save/restart walkthrough require user testing.

### Build results

- Unity: **739 checks passed** — 45 knowledge/inspector, 298 assembly (real 39-part
  drone), 31 prayer, 284 workspace, 66 legacy, and 15 runtime/manifest.
- Python: **46 tests passed**. No generation service restart or paid provider calls.
- Final Android build: Unity exit 0, 36.68 seconds. Signature verified, version
  **1.9 / code 10**. Log: `/private/tmp/oryn-knowledge-final-build.log`.
- APK SHA-256: `2e684bd06755129f261b4bc7320f7e904e83b7075bae80e0aad01862e83e5a42`.
- Installed with app data retained and launched on Quest. Package manager confirms
  version 1.9 / code 10. Existing drone USB delivery:
  `98e9c621aaa84a07a9478dcaedfe8585`; receipt state is tracked in
  `.oryn-generation/194f107aee2550dd9369453ad3fe6bb8/island-analysis/quest-knowledge-delivery-v1.9.json`.
- Rendered `Builds/Preview/Workspace.png` and `Builds/Preview/PartInspector.png`
  inspected for button/text overlap, including a long preset label and clear draft.
- The actual model was imported twice from different filenames in tests; its 39
  geometry addresses remained identical, and the annotation resolved to the same part.
  This is automated editor verification, not a claim of a completed user headset test.
