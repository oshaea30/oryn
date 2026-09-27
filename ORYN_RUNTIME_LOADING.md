# Runtime model loading — original roadmap milestone 3

## Current implementation

The original brief's next milestone after manipulation is loading a GLB that was NOT
compiled into the app. (The existing `MilestoneThreeWorkspace` scene name predates this
roadmap alignment; it remains the active scene.) This pass adds that capability locally,
without generation, AI, voice, networking, or an orchestrator.

Unity glTFast **6.20.0**, a stable release compatible with Unity 6, owns glTF parsing,
mesh/texture creation and scene instantiation. `OrynRuntimeModel` owns imported resources
and normalizes the longest dimension to 35 cm when adopted by the workspace. Existing
workspace state owns selection, movement, rotation and scaling. Geometry is replaceable
without changing the input system. No custom 3D format/parser was introduced.

References: [glTFast runtime loading](https://github.com/Unity-Technologies/com.unity.cloud.gltfast/blob/main/Packages/com.unity.cloud.gltfast/Documentation~/ImportRuntime.md)
and [shader setup](https://github.com/Unity-Technologies/com.unity.cloud.gltfast/blob/main/Packages/com.unity.cloud.gltfast/Documentation~/ProjectSetup.md).
The three glTF built-in shaders are retained in Graphics Settings to avoid missing
materials after IL2CPP/shader stripping. External cameras, lights and animations are
not instantiated.

## First fixture and transfer

`RuntimeAssets/Avocado.glb` is Microsoft's CC0 Avocado, sourced through Khronos sample
assets. It is outside Assets, Resources and StreamingAssets, so it is NOT compiled into
the APK. Attribution/source are in `RuntimeAssets/README.md`.

Fixture SHA-256: `ccc9c3ce56423720b09399c2351537207cd5a65f859f9e6e2f30922762f3abd4`.

After installing the app, copy the fixture separately:

```sh
ADB='/Applications/Unity/Hub/Editor/6000.6.3f1-arm64/PlaybackEngines/AndroidPlayer/SDK/platform-tools/adb'
"$ADB" -s 1WMHHA6DVJ1472 shell mkdir -p /sdcard/Android/data/com.oryn.milestoneone/files/Imports
"$ADB" -s 1WMHHA6DVJ1472 push RuntimeAssets/Avocado.glb /sdcard/Android/data/com.oryn.milestoneone/files/Imports/model.glb
```

Launch Oryn Workspace. After headset tracking initializes, the cube appears and one
external model loads beside it. `LOAD MODEL` loads another copy from the same path,
including after replacing the file. It disables while an import is in progress. Keep a
clear nearby spawn slot; existing objects are never moved to make room. Missing or bad
files show a short panel error and log `ORYN_MODEL_FAILED`, without removing objects.

The thin interaction box is intentional: move/rotate/resize the model using its bounds.
The model itself retains its authored textures/materials. Delete releases importer-owned
meshes/textures/materials; Reset restores size/nearby placement. Workspace layouts remain
session-only; the source GLB file stays on disk for later loads.

## Deliberate limits

- Trusted, self-contained GLB 2.0 only, under 16 MB. No arbitrary URL/file browser.
- Referenced external buffers/textures are rejected by an injected download provider.
- Static mesh prototype: 1–128 renderers, at most 200,000 counted vertices. Skinned
  models, animation playback, Draco/Meshopt compressed geometry and KTX textures are
  outside this pass. Limits are not a hardened sandbox for hostile assets.
- Imported contact is a normalized bounding box, not exact mesh collision or articulated
  grasping. No semantic parts, slicing, exploded view, persistence or room anchors yet.
- Resize repair preserves thumb+index with BOTH hands; one-hand radial resizing is not
  implemented. Hand-tracking feel still requires physical testing.

## Verification

Build with the asynchronous editor validation runner (intentionally no `-quit`):

```sh
'/Applications/Unity/Hub/Editor/6000.6.3f1-arm64/Unity.app/Contents/MacOS/Unity' \
  -batchmode -force-metal -buildTarget Android \
  -projectPath '/Users/oshaealexis/Developer/Oryn/Unity-StarterSamples' \
  -executeMethod Oryn.Editor.OrynRuntimeModelTests.ValidateAndBuild \
  -logFile /private/tmp/oryn-runtime-build.log
```

The runner exits on completion/failure; it loads the real external file, renders
`Builds/Preview/RuntimeModel.png`, runs the interaction checks and builds the APK. It does
not add the imported model to any saved scene. Panel preview: `Builds/Preview/Workspace.png`.

Headset acceptance: confirm a textured model appears; select/move/rotate/resize it; delete
and reload it; replace the file without rebuilding and load again. Device logs distinguish
`ORYN_MODEL_PARSED` from `ORYN_MODEL_LOADED` (adopted into the workspace). No mathematical
or desktop test alone satisfies headset manipulation acceptance.

### 2026-09-26 build record

- 10 runtime-loading checks and 350 interaction checks passed; model and panel renders
  inspected. The sample renders with its green texture, not a missing-material shader.
- Final Android build: 33.6 seconds, editor exit 0; APK signature verified.
- Version 1.5 / Android code 6; same application ID as the earlier prototype.
- APK SHA-256: `54757fe1f36cb82afa579f256531d45d7bb7ed5d6d91e64c5b8e666dd215ea65`.
- External GLB copied separately to Quest app storage; device SHA-256 matched the source.
- Installed successfully; launch returned `Status: ok`; Quest reports version 1.5/code 6.
- Quest startup logged `ORYN_MODEL_PARSED name=model.glb bytes=8110040` and then
  `ORYN_MODEL_LOADED source=external_file seconds=0.28`. This verifies actual Android
  runtime import and workspace adoption, not just editor import. No import exception
  appeared in the startup sample. Physical rendering/gesture acceptance remains pending.
- Log: `/private/tmp/oryn-runtime-build-final.log`. The physical gesture result is not assumed.

## Next priority (updated by user)

The user confirmed external loading, manipulation and resizing, then explicitly moved
prompt-based asset generation ahead of multipart interactions. See ORYN_GENERATION.md.
Explode/reassemble and semantic object structure are deferred, not the current next step.
