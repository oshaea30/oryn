# ORYN

An experimental spatial workspace for generating, manipulating, and investigating
3D objects on Meta Quest. Geometry generation is separate from ORYN's persistent
object knowledge and validated runtime actions.

## Current checkpoint

- Unity/Quest passthrough workspace with controller and hand manipulation.
- Runtime GLB import, mesh-island inspection, part selection, isolation, and
  prayer-to-spread assembly explosion/reassembly.
- Persistent part labels with provenance: user annotations remain unverified,
  not automatically recognized mechanical components.
- Local Meshy generation adapter with separate geometry, optional texturing,
  inspection, and confirmed USB delivery steps.
- Text-command lab with offline test interpretation, provider adapters, grounded
  record lookup, explicit action confirmation, and headset execution receipts.
- Persistent local command spending reservations, expiring quotes, bounded
  requests, and no automatic paid retries. See the spending guide for scope and
  limits; this is not an account-wide provider billing cap.

This is a trusted-local-user prototype, not a production multi-user service.
Schematic retrieval, automatic component understanding, voice, and production
authentication are not implemented. Live cognitive-provider evaluation remains
pending; mocked tests do not establish provider compatibility or answer quality.

## Development

Open this repository in Unity **6000.6.3f1** with Android build support. Package
versions are recorded in `Packages/manifest.json` and `Packages/packages-lock.json`.
The active build scene is `Assets/Oryn/Scenes/MilestoneThreeWorkspace.unity`.
Meta XR Core, OpenXR, and glTFast remain required dependencies.

The local services use Python 3 and its standard library. From the repository root,
run either service in its own terminal:

```sh
python3 Orchestrator/app.py          # Generation lab: http://127.0.0.1:8765/
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

Configure API keys only through the local service's in-memory settings. Do not
commit credentials. Generated jobs, usage databases, Unity caches, builds, crash
dumps, and local environment files are excluded from version control. Restarting
a service clears its in-memory key; it does not clear persistent spending records.

## Guides

- [Quest setup](ORYN_MILESTONE_1.md) and [local preview](ORYN_LOCAL_PREVIEW.md)
- [Workspace and controls](ORYN_WORKSPACE.md)
- [Runtime model loading](ORYN_RUNTIME_LOADING.md) and [generation](ORYN_GENERATION.md)
- [Assembly interactions](ORYN_ASSEMBLIES.md) and [object knowledge](ORYN_KNOWLEDGE.md)
- [Text commands](ORYN_COMMANDS.md) and [spending guardrails](ORYN_SPENDING.md)

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
