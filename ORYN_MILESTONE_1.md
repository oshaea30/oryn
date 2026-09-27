# Oryn Milestone 1: Quest Passthrough Object

## Scope

This milestone proves one capability only: a stationary virtual cube can be rendered over the physical room on a Meta Quest 2.

It contains no AI, networking, runtime asset loading, voice, grabbing, room understanding, or backend services.

## Current design

- XR standard: Unity OpenXR
- Platform integration: Meta XR Core SDK, limited to camera tracking and passthrough
- Scene: `Assets/Oryn/Scenes/MilestoneOnePassthrough.unity`
- Object: a 35 cm blue cube at `(0, 1.35, 1.75)` metres in stage space
- Tracking origin: Stage
- Android application ID: `com.oryn.milestoneone`
- Android architecture: ARM64
- Scripting backend: IL2CPP
- Minimum Android API: 32
- Target Android API: 34
- Graphics API: Vulkan

## Prerequisites

- Unity Hub
- Unity `6000.6.3f1` Apple Silicon (the installed editor used by this working copy)
- Android Build Support for that editor
- Unity-provided Android SDK & NDK Tools
- Unity-provided OpenJDK
- Meta Quest 2 with Developer Mode enabled
- A data-capable USB-C cable

## Configure the scene

From the project root:

```sh
UNITY="/Applications/Unity/Hub/Editor/6000.6.3f1-arm64/Unity.app/Contents/MacOS/Unity"
"$UNITY" -batchmode -nographics -quit \
  -projectPath "$(pwd)" \
  -executeMethod Oryn.Editor.OrynMilestoneOneSetup.Configure \
  -logFile -
```

The setup is repeatable: running it again recreates the scene and reapplies the required build settings.

## Build the APK

From the project root:

```sh
UNITY="/Applications/Unity/Hub/Editor/6000.6.3f1-arm64/Unity.app/Contents/MacOS/Unity"
"$UNITY" -batchmode -nographics -quit \
  -projectPath "$(pwd)" \
  -executeMethod Oryn.Editor.OrynMilestoneOneSetup.BuildAndroid \
  -logFile -
```

The ignored build artifact is written to `Builds/Android/OrynMilestoneOne.apk`.

`BuildAndroid` preserves the authored scene. Use `ConfigureAndBuildAndroid` only when
you intentionally want to regenerate the default scene before building. Close this
project's Unity editor before running a batch build.

## Connect and deploy

### Latest build: 2026-09-26

- Scene-preserving Android build completed in Unity 6000.6.3f1 (181 seconds, 42 warnings).
- APK: 53,581,291 bytes; package `com.oryn.milestoneone`, ARM64, API 32 minimum / 34 target.
- APK signature verification passed (v2). Passthrough capability is declared in the manifest.
- SHA-256: `cb7a99a5fdedf1286ce3c0b938444a4ed87b843726ce89c7ba0fc07aa91a3e13`.
- Unity reported build success, then crashed during asset-database shutdown (process exit 139).
  The finished APK was independently inspected and signature-verified before deployment.
- Temporary build log: `/private/tmp/oryn-quest-deploy-build.log`.
- Installed on the connected Quest 2 using ADB (`Success`); launch returned `Status: ok`.
- App process stayed running. Startup logs reported `TrackingAcquired` and
  `XR_TYPE_EVENT_DATA_PASSTHROUGH_LAYER_RESUMED_META`.
- User subsequently reported seeing the blue cube hovering in the room and remaining
  fixed in place as they moved. This is the working baseline for the next milestone.
- Controller/hand interaction is developed separately; see [interaction notes](ORYN_INTERACTION.md).

### Deployment steps

1. Enable Developer Mode for the Quest 2 in the Meta Horizon mobile app.
2. Power on the headset and connect it with a data-capable USB-C cable.
3. Put on the headset and approve the USB debugging prompt. Select **Always allow from this computer** if desired.
4. Verify the connection:

   ```sh
   adb devices -l
   ```

5. Install or replace the development build:

   ```sh
   adb install -r Builds/Android/OrynMilestoneOne.apk
   ```

6. Launch **Oryn Milestone 1** from the headset's applications list under unknown/development sources.

## Physical acceptance test

- The application launches on the Quest 2.
- The physical room is visible through grayscale passthrough.
- One blue cube is visible approximately 1.75 m in front of the initial stage origin.
- Moving the head produces correct perspective and parallax.
- The cube remains stable relative to the tracked Unity world during the session.

Milestone 1 is not complete until all five checks pass on the physical Quest 2.

For development without a headset, see [the local preview guide](ORYN_LOCAL_PREVIEW.md).
Desktop verification does not satisfy these physical acceptance checks.

## Troubleshooting boundary

If `adb devices -l` shows no device, the missing interface is the USB/debugging connection rather than Unity scene logic. Reconnect the cable, unlock the headset, and approve the in-headset USB debugging prompt before rebuilding.
