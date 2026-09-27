# Oryn local development

## Working copy

Use `/Users/oshaealexis/Developer/Oryn/Unity-StarterSamples` with Unity **6000.6.3f1 Apple Silicon**.
The original under `Documents/OpenProjects/Oryn` remains a reference copy. Its iCloud-offloaded
assets stalled imports, so active development now uses a local copy outside Documents.
This copy starts at official Starter Samples commit `2fe7032` (Meta SDK 205), with the existing
Oryn scene, scripts and materials carried across. It is on branch `codex/local-preview`.

## Preview

1. Open this folder as a Unity project.
2. Select **Oryn > Local Preview > Open and Play**.
3. Click inside the Game view to focus it.
4. Use **WASD** to move, **Q/E** to descend/ascend, hold **right mouse** to look,
   hold **Shift** to move faster, and press **R** or **Reset view** to return.
5. Stop Play mode before editing the source scene.

The generated scene is `Assets/Oryn/Scenes/LocalPreview.unity`.
It copies the existing Quest scene, replaces the headset rig with a desktop camera,
and adds a synthetic 6 m by 7 m room with a one-metre floor grid.
The cube stays at the same position and scale as the Quest scene.
There is no live camera feed, XR input simulation, AI, or backend.

The generated preview is disposable: edit the original
`Assets/Oryn/Scenes/MilestoneOnePassthrough.unity`, then use **Recreate from Quest Scene**.
Changes made only to the preview scene will be replaced when it is recreated.

## Platform boundary

The preview selects the Mac build target and turns off automatic XR startup for **Standalone**.
Android's XR configuration remains separate. The preview scene is not in the Quest build list.
To rebuild the Quest prototype, run `Oryn.Editor.OrynMilestoneOneSetup.BuildAndroid`
with the installed editor path below. That selects Android and configures the original
single-cube passthrough scene without regenerating it. Close this project in Unity first.
The separate `ConfigureAndBuildAndroid` command regenerates the prototype scene;
save authored changes separately before deliberately running that command.

```sh
UNITY='/Applications/Unity/Hub/Editor/6000.6.3f1-arm64/Unity.app/Contents/MacOS/Unity'
PROJECT='/Users/oshaealexis/Developer/Oryn/Unity-StarterSamples'
"$UNITY" -batchmode -quit -projectPath "$PROJECT" \
  -executeMethod Oryn.Editor.OrynMilestoneOneSetup.BuildAndroid \
  -logFile /private/tmp/oryn-quest-build.log
```

## Verification

Close this project in Unity before running an automated check:

```sh
UNITY='/Applications/Unity/Hub/Editor/6000.6.3f1-arm64/Unity.app/Contents/MacOS/Unity'
PROJECT='/Users/oshaealexis/Developer/Oryn/Unity-StarterSamples'
"$UNITY" -batchmode -force-metal -projectPath "$PROJECT" \
  -executeMethod Oryn.Editor.OrynLocalPreviewSetup.VerifyPlayMode \
  -logFile /private/tmp/oryn-local-preview-test.log
```

Do not add `-quit` or `-nographics`: verification enters Play mode, renders a frame,
and exits itself. It checks camera movement, perspective/parallax, reset, stationary object,
absence of Meta camera components, and exclusion of the preview from the Quest build list.
A successful run emits `ORYN_LOCAL_PLAYMODE_OK` and writes
`Builds/Preview/LocalPreview.png` (camera image only, without the controls overlay).

Verified locally on 2026-09-26 with Unity 6000.6.3f1: Play mode exited successfully,
movement/parallax/reset/stationary-cube checks passed, and the rendered image was visually
inspected. The final log is `/private/tmp/oryn-local-preview-final-test.log` (temporary).
No new Android APK was built in this pass, and no physical headset test was performed.

## Meta XR Simulator (separate, optional)

The plain desktop preview works without installing Meta XR Simulator.
The current simulator is a separate OpenXR runtime, available for Apple Silicon macOS:
https://developers.meta.com/horizon/downloads/package/meta-xr-simulator-mac-arm/

For XR simulation, use the **Quest scene**, re-enable **Initialize XR on Startup** for
Standalone under Project Settings > XR Plug-in Management, ensure OpenXR is enabled there,
and follow Meta's activation instructions. Choose the Quest 2 device profile when available.
Running the desktop-preview menu disables Standalone XR startup again.

https://developers.meta.com/horizon/documentation/unity/unity-simulate-xrsim/

Simulation is not Android execution and does not verify physical tracking or actual passthrough.
Milestone 1 still requires the physical Quest 2 acceptance test in `ORYN_MILESTONE_1.md`.

## Editor migration notes

Unity upgraded its bundled packages when opening the older sample in 6000.6.3f1.
Two missing OpenXR feature references were removed and supported feature types refreshed;
valid enabled features were preserved. The repair is available under **Oryn > Tools**.
Unity 6000.6.3f1's Search startup indexer threw an empty-index exception in this project.
`UserSettings/Search.settings` has `indexOnEditorStartup` set to `false` locally to avoid it.
This preference is ignored by Git; on another checkout, disable **Index on Editor Startup**
in Search preferences if the same editor error occurs. This does not disable application rendering.
The desktop camera hides the sample's world-space debug console during preview startup;
the Quest scene's debugger settings are not changed.

## Design decision

**Decision:** A generated desktop view of the existing Quest scene.
**Why:** Make the current cube visible and navigable with no headset or new SDK dependency.
**Alternatives:** Meta XR Simulator for XR-specific testing; a separate browser renderer.
**Impact:** The same Unity source content drives both views, with a disposable preview room
and camera. Hardware validation and future object interaction remain separate milestones.
