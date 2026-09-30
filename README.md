# ORYN

An experimental spatial workspace for generating, manipulating, and investigating
3D objects on Meta Quest. Geometry generation is separate from ORYN's persistent
object knowledge and validated runtime actions.

## Current priority

The controlled PartCrafter framing comparison is complete. Tighter framing made
the drone more recognizable but did not meet the frozen improvement threshold for
visual quality and useful components. Paid trials of this configuration are stopped.
See the [comparison result](Research/native_objects/FRAMING_RESULT.md) and
[working roadmap](ORYN_ROADMAP.md). Next is an evidence-based assessment of an
alternative generation approach before another paid run. The Quest product stays
stable; general answering, voice, training and motion inference are paused.

## Complete Object integration preview

The default local page now routes typed requests through ORYN’s own bounded
OpenAI interpreter, authored-object knowledge, persistent conversation journal
and validated Quest transport. The first object is the authored drone. Run
`Orchestrator/app.py`; generation/settings remain at `/objects`, labs at `/lab`
and port 8767. This requires the updated Quest build and the existing OpenAI
research connection. See [Complete Object v1](ORYN_COMPLETE_OBJECT.md).
Voice, polished geometry and uncoached Quest acceptance remain future gates;
the typed integration is not a completed MVP.

## Current checkpoint

- Unity/Quest passthrough workspace with controller and hand manipulation.
- Runtime GLB import, mesh-island inspection, part selection, isolation, and
  prayer-to-spread assembly explosion/reassembly.
- Persistent part labels with provenance: user annotations remain unverified,
  not automatically recognized mechanical components.
- Single-submit object requests: exact saved match or bounded Meshy geometry,
  automatic inspection and USB delivery, with no per-request approvals.
  The staged developer lab remains available at `/lab`.
- Versioned ingestion manifests, lossless assembly preparation for supported layouts,
  and explicit capability limits. Geometry pieces remain distinct from components.
- Text-command lab with offline test interpretation, provider adapters, grounded
  record lookup, explicit action confirmation, and headset execution receipts.
- Persistent local command spending reservations, expiring quotes, bounded
  requests, and no automatic paid retries. See the spending guide for scope and
  limits; this is not an account-wide provider billing cap.

This is a trusted-local-user prototype, not a production multi-user service.
Schematic retrieval, automatic component understanding, voice, and production
authentication are not implemented. One live OpenAI reassembly request passed
interpretation, execution and 39-part state verification; this is not broad
cognitive-provider validation. Automatic object requests are tested offline;
the new end-to-end user experience still needs a live generation check.

## Development

Open this repository in Unity **6000.6.3f1** with Android build support. Package
versions are recorded in `Packages/manifest.json` and `Packages/packages-lock.json`.
The active build scene is `Assets/Oryn/Scenes/MilestoneThreeWorkspace.unity`.
Meta XR Core, OpenXR, and glTFast remain required dependencies.

The local services use Python 3 and its standard library. From the repository root,
run either service in its own terminal:

```sh
python3 Orchestrator/app.py          # Object requests: http://127.0.0.1:8765/ (lab at /lab)
python3 Orchestrator/command_app.py  # Command lab: http://127.0.0.1:8767/
```

Quest delivery and commands require Android Debug Bridge (ADB), an authorized USB
connection, and ORYN installed/open. See the milestone guides for build and device
setup. Existing local model caches and generated jobs are not part of this repo;
`RuntimeAssets/Avocado.glb` is the included no-generation import fixture.

Run the local Python suite without paid provider calls:

```sh
python3 -m unittest discover -s Orchestrator -p 'test_*.py' -v
node --check Orchestrator/command.js
```

Configure API keys through the local services. Meshy is stored in macOS Keychain
under service `com.oryn.local-generation`, account `meshy-api-key`, and restored
automatically at startup. The command lab's language-provider keys still live only
in memory. Do not commit credentials. Generated jobs, usage databases, Unity caches,
builds, crash dumps, and local environment files are excluded from version control.
Restarting does not clear persistent spending records.

## Guides

- [Working roadmap and storage direction](ORYN_ROADMAP.md)
- [Quest setup](ORYN_MILESTONE_1.md) and [local preview](ORYN_LOCAL_PREVIEW.md)
- [Workspace and controls](ORYN_WORKSPACE.md)
- [Runtime model loading](ORYN_RUNTIME_LOADING.md) and [generation](ORYN_GENERATION.md)
- [Assembly interactions](ORYN_ASSEMBLIES.md) and [object knowledge](ORYN_KNOWLEDGE.md)
- [Object ingestion manifest and preparation](ORYN_INGESTION.md)
- [Text commands](ORYN_COMMANDS.md) and [spending guardrails](ORYN_SPENDING.md)
- [XR inspection and guarded assembly regression](ORYN_XR_INSPECTION.md)

## Starter provenance

ORYN began from [Meta Unity Starter Samples](https://github.com/oculus-samples/Unity-StarterSamples).
This repository preserves the upstream history and starter assets as a checkpoint;
ORYN's active scene and code live under `Assets/Oryn`, not the starter demo scenes.
Removing unused starter assets is a separate build-tested cleanup. The local folder
name may still be `Unity-StarterSamples`; it does not determine the app's identity.

The original [upstream README](UPSTREAM_README.md), [Meta MIT license](LICENSE),
and component-specific notices are retained. Audio360 has its own terms under
`Assets/StarterSamples/Core/Video/Plugins/Android/Audio360`. The included avocado
fixture has [separate CC0 attribution](RuntimeAssets/README.md).
