# Oryn: controller and hand grabbing

This is the M2 baseline. The current two-handed, multi-object version is documented
in [Oryn Workspace](ORYN_WORKSPACE.md) and has its own M3 scene.

## What this adds

The separate `Assets/Oryn/Scenes/MilestoneTwoInteraction.unity` scene copies the working
passthrough milestone, adds tracked hands, and supports near-grab manipulation of its cube.
The original `MilestoneOnePassthrough.unity` is preserved.

- Controllers: move either controller close to the cube, squeeze its **side grip trigger**,
  move/rotate it, then release. The index trigger is not the grab input.
- Bare hands: put controllers down and let the Quest switch to hand tracking. Bring an
  open hand close to the cube, pinch thumb and index finger together, move/rotate, then
  open the pinch to release. Use either hand. Hand tracking must be enabled on the Quest.
- Blue = idle, mint = near enough to grab, gold = held. A small white marker shows the
  measured grip/pinch location. Reach within 10 cm of the cube's surface before grabbing.
- The cube appears 65 cm ahead and 25 cm below the user's initial head position.
  **B** on the right controller or **Y** on the left brings it back within reach.
- Released objects stay suspended. Open the grip/pinch before trying again after tracking
  loss, input-mode switching, a system gesture, or opening the headset menu.

Both input modes are supported, but simultaneous mixed controller/hand use is not promised
on Quest 2: normal system-controlled switching is the acceptance target.
Stay in a clear area and mind the USB cable; no walking across the room is needed to reach the cube.

## Deliberate limits

This is near-grab/pinch manipulation, not a physics-hand simulation. An unpinched hand
can pass through the cube. There is no pushing, throwing, gravity, two-hand scaling,
collision with real furniture, scene understanding, or persistence across app restarts.
Tracking loss releases ownership and freezes the last valid pose rather than applying
an untrusted hand pose. Opening a system menu also releases the object.

## Design decision

**Decision:** Use the installed Meta Core hand/controller APIs and one small,
device-independent grab state machine for this single-object milestone.
**Why:** Reuses the verified rig, avoids new dependencies on a nearly full disk, and
makes ownership, offsets, release, and tracking-loss behavior directly testable.
**Alternatives:** Meta Interaction SDK provides standardized richer interactions and is
the appropriate option to evaluate before expanding into many interaction types.
**Impact:** This is a bounded prototype, not a replacement for that SDK. Meta-specific
input stays in `OrynDualInputGrab`; pose/ownership logic stays in `OrynGrabState`.
It does not add a backend, AI, networking, or room access.

Hand validity/confidence checks follow the installed SDK and
[Meta's hand interaction guidance](https://developers.meta.com/horizon/documentation/unity/unity-handtracking-interactions/).
The hand skeleton and mesh types are selected from the project's configured skeleton
version, supporting both legacy OVR and OpenXR fingertip IDs.

## Build and verification

Close this project in Unity first. The build creates the interaction scene only when
missing; subsequent builds preserve authored changes. It replaces the installed
`com.oryn.milestoneone` app with version 1.1 (version code 2), named **Oryn Interaction**.

```sh
UNITY='/Applications/Unity/Hub/Editor/6000.6.3f1-arm64/Unity.app/Contents/MacOS/Unity'
PROJECT='/Users/oshaealexis/Developer/Oryn/Unity-StarterSamples'
"$UNITY" -batchmode -quit -nographics -buildTarget Android -projectPath "$PROJECT" \
  -executeMethod Oryn.Editor.OrynInteractionSetup.BuildAndroid \
  -logFile /private/tmp/oryn-interaction-build.log
```

Artifact: `Builds/Android/OrynInteraction.apk`.
The build runs deterministic grab checks first, then validates the scene references.
Tests can also be run through **Oryn > Interaction > Run Grab Logic Checks** or batch
`-executeMethod Oryn.Editor.OrynInteractionSetup.RunTests`.

Checks cover all four input sources, fresh-grab requirements, no acquisition snap,
translation/rotation offsets, hysteresis, exclusive ownership, near-distance gating,
release, tracking loss/recovery, switching sources, focus/pause release, and reset.
These tests simulate input; they do not prove real headset gesture quality.

## Physical acceptance (pending)

### Verification on 2026-09-26

- 66 automated grab/proximity checks passed; scene reference checks passed.
- Final Android build succeeded in 32 seconds, editor exit code 0; APK signature verified.
- SHA-256: `32a66d10ca40bfdb9bf2c809a184986fc40d086b451d095245c74996a6bb35f6`.
- Installed on Quest 2 (`Success`) and launched (`Status: ok`). Runtime emitted
  `ORYN_M2_READY` and `ORYN_M2_RESET`; the process remained alive.
- A first-device-test marker error caused by stripped `SphereCollider` was corrected:
  markers now reference a serialized mesh and do not create runtime primitive colliders.
  The corrected launch did not repeat that error.
- Unity logged an Android `AssetPackManager` class lookup error during startup, then
  continued into XR and the interaction scene. No fatal crash was observed; this message
  remains a follow-up if any asset-loading issue appears during physical testing.
- Original M1 scene SHA-256 remained unchanged:
  `b9049fabeaa2f6204867c0156b25be767acae7ed607d91549eaebbe3cc471a6e`.
- Final temporary build log: `/private/tmp/oryn-interaction-build-final.log`.
- Real left/right controller grips and hand pinches still require the user's test below.
- Mac free disk space is approximately 2 GB; plan space recovery before larger builds.

### Headset checklist

1. Real room and cube remain visible; there is no desktop room in the headset build.
2. Each controller can grab with its side grip, move/rotate, and release.
3. Each bare hand can pinch near the cube, move/rotate, and release.
4. Cube remains stationary after release and changes color appropriately.
5. Switching between controllers and hands does not jump or lock the cube.
6. Covering a tracked hand or opening the system menu safely releases it.
7. B/Y reset returns the cube within reach and clears ownership.

Milestone 2 is not complete until the user verifies these on the Quest.
