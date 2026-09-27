# Oryn workspace: objects and two-handed manipulation

## Use in the Quest

The app is now **Oryn Workspace**, version 1.9.2 (Android version code 12), updating the
same `com.oryn.milestoneone` development package. M1 and M2 scenes remain as baselines;
the active scene is `Assets/Oryn/Scenes/MilestoneThreeWorkspace.unity`.

Version 1.7 adds **PARTS / WHOLE**, **EXPLODE**, **ISOLATE / ALL**, and **ASSEMBLE**
for multi-mesh runtime models. See [assembly controls and verification](ORYN_ASSEMBLIES.md).
Part reset returns it to its assembly-relative home; individual part deletion is
disabled. Whole-object deletion retains confirmation. Pinch-resize gesture/math is
unchanged; the user's reported feel regression remains open.

Version 1.8 adds **prayer-to-spread**: release the drone, hold open palms facing each
other with fingers up and a small gap briefly, then move hands apart/together to
control part spread. Turn palms away to stop. No button press is needed; see the
assembly guide for selection, range, and reset behavior. This does not resize parts.

Version 1.9 adds the [persistent part inspector](ORYN_KNOWLEDGE.md). Select a piece,
choose a draft label, then SAVE it as an unverified user annotation. The last annotated
model reopens after restart with its records; scene poses and part layouts are not saved.

Version 1.9.2 fixes model recovery: **BRING MODEL** replaces the legacy LOAD MODEL
button. It reassembles and brings the selected assembly (or most recently imported
assembly if a primitive/demo is selected) within reach without requiring a grab.
If only single-mesh models exist, it recovers the selected/latest imported model.
With nothing loaded, it tries the saved model; it never silently loads the old avocado.
New generated USB deliveries are cached for restart even before any labels are saved.
There is no automatic startup cube or legacy avocado import. New objects/recovery
are 45 cm ahead and 8 cm below eye level, independent of head pitch. This is not
furniture collision detection: face a clear space before bringing the model there.

- **Touch first:** bring a fingertip or palm to a face, edge, or corner. The object
  highlights mint and the white marker lands on its surface. Close the gesture at
  that contact; the contact can precede the pinch by up to 300 ms. A pinch just before
  contact also has a 300 ms acquisition window. Closing in midair long before reaching
  the object does not acquire it; open and try again. Panel activation stays fresh-press only.
- **Move / rotate:** bring your thumb and at least two fingertips together at the
  object (thumb + index + middle is the easiest starting gesture). Use one or both
  hands. Size stays locked even when you spread your hands. With two hands, changing
  the line between the hands rotates the object; conflicting wrist rolls are ignored.
- **Resize:** pinch thumb and index finger with EACH hand near the same object (up
  to 15 cm outside its surface; surface contact is NOT required), then
  pull your hands apart or together. Size changes while position and rotation stay
  fixed. One two-finger pinch waits for the second hand; it does not move the object.
  The distance comes from the actual pinch positions, independently of the surface
  anchors used for holding. A captured resize remains active as the hands move away.
- **Controllers:** side grip = move/rotate; index trigger without side grip = resize.
  Use both index triggers to resize. Side grip takes priority when both are squeezed.
  When pointing at a menu button, trigger or A/X activates the button instead.
- Gold = moving/rotating, purple = resizing, teal = waiting for a second pinch or
  matching/stable gestures. The panel also names the active operation.
- Add/remove a fingertip to change operations without releasing the object. Switching
  operations captures a fresh baseline so size/pose cannot jump. Different gestures
  between hands pause manipulation until they match.
- During three-finger manipulation, release either hand to continue with the other;
  release both to leave the object suspended. Grip offsets and scale survive handoff.
- Each hand may instead grab a different object. One source cannot hold two objects,
  and a hand plus its corresponding controller cannot impersonate two hands.
- **Menu (1.9.1):** look toward where you want the menu and press **B/Y**. It appears
  upright, 70 cm ahead and 23 cm below eye height, including while seated. Head pitch
  does not drive it toward the floor. The workspace and inspector are centered together.
  This only repositions the menu; it no longer resets the selected object.
- Aim a free controller at a button. A pointer line and surface marker appear when
  aimed at a button; pull the **index trigger** or press **A/X** to activate it.
  Pointing works up to 2.5 m and from the front of the panel. Disabled actions remain
  disabled, and DELETE retains its two-press confirmation.
- Hand interaction remains near-button pinch/grip. Controller near-button interaction
  now uses trigger/A/X rather than side grip. Touch alone and held inputs do not
  activate/repeat commands; focus recovery/recentering require a fresh press.
- **+ Cube / + Sphere** creates and selects an object. Up to 12 objects are allowed.
  Spawn uses three clear nearby slots; if all are occupied, move an existing object
  aside first. Creation never moves existing objects or puts new objects far away.
- **Bring Model** recovers the existing imported model, not a fresh copy of the
  legacy `Imports/model.glb` demo. Startup restores the remembered model when available.
  Imported models use a visible bounding-box interaction proxy, not exact mesh contact.
  See [runtime-loading notes](ORYN_RUNTIME_LOADING.md) for file transfer and limits.
- **Delete** applies to the selected object named above the buttons. Activate Delete
  again with the same hand within four seconds to confirm; it removes that session
  object only. It cannot be undone, but the shape can be recreated.
- **Reset Selected** restores the selected object's original size and puts it within
  reach. **B/Y** repositions only the menu and preserves object/part state.

Hand visuals now use a separate render-only skeleton with bounded palm/finger surface
correction. Raw tracking still controls gesture recognition and object motion. The
white marker stays at the object's captured local surface anchor while held. Contact
never activates a panel command or moves an object without the requested gesture.

Normal Quest switching between controllers and bare hands is supported. Mixed use of
one physical controller and one bare hand at once depends on platform support and is
not promised on Quest 2. Stay aware of the cable and physical surroundings.

## Limits and decisions

**Decision:** A separate workspace scene, batch-sampled input, and a device-independent
two-hand transform state. **Why:** The original exclusive-owner model could not support
natural handoff or two-handed edits. **Alternatives:** Meta Interaction SDK remains a
candidate for a richer production interaction system. **Impact:** M1/M2 remain intact;
the small workspace implementation can be tested without tracking hardware.

The current gesture split follows the user's physical test feedback: automatic scaling
competed with positioning, and wrist-based rotation could turn abruptly. Three-or-more
fingers means thumb plus at least two fingertips, as confirmed by the user.

Two-finger resizing uses relative hand span, with a 2 cm dead zone and light smoothing;
it cannot translate or rotate the object. Three-finger manipulation uses midpoint
translation and incremental changes in the hand-to-hand direction, not averaged wrist
orientation. Translation is smoothed and speed-limited to 2 m/s; rotation to 240 degrees/s.
A single-frame hand-direction reversal over 100 degrees is rejected and rebased.
Each ownership or operation change rebases against the existing pose. Scaling remains
bounded from 25% to 300% of the initial 35 cm shape. A span under 6 cm freezes the transform;
recovery takes a fresh baseline rather than jumping from the collapsed span.
Finger pinch states use separate engagement/release thresholds and a short settling
period (80 ms for manipulation, 150 ms for resizing). Unknown extra-finger tracking is
not treated as an open finger and cannot silently enable resizing.
Loss of one tracked hand hands off to the other; losing both or opening a system menu
releases the object. A fresh open-then-grip/pinch is needed after tracking recovery.

Objects are session-only: no saved layouts or real-world spatial anchors yet. There
is no gravity, pushing, furniture collision, throwing, AI, or external service.
This is a **bounded near-surface contact prototype**, not a full physics-hand solver:
fingertip targets correct by at most 4.5 cm, each visual joint by 35 degrees, and palm
offset by 3.5 cm. Bone lengths are preserved. Deeply pushing a real hand through an
object can still show penetration; the solver does not dislocate or stretch the hand
to guarantee nonpenetration. No bare-hand force feedback or controller haptics are added.
Object acquisition uses thumb/four fingertip/palm samples with 2.5 cm outside tolerance
and 1.5 cm inside tolerance, not the old 10 cm pinch-point proximity. Surface crossings
under 15 cm between valid frames are detected; tracking teleports/deep startup overlaps
are rejected. Collider queries handle rotated/scaled boxes and spheres, including inside
points. Holds follow a stable palm pose with a captured surface offset; changing the
number of pinching fingers no longer changes the tracking origin. The visual skeleton
is restored on focus/tracking loss and rebuilt when the provider skeleton changes.
Reset affects the selected object, not the whole workspace. Delete confirms rather
than immediately destroying the selected object on one accidental input.

## Build

Close the project in Unity before the batch command:

```sh
UNITY='/Applications/Unity/Hub/Editor/6000.6.3f1-arm64/Unity.app/Contents/MacOS/Unity'
PROJECT='/Users/oshaealexis/Developer/Oryn/Unity-StarterSamples'
"$UNITY" -batchmode -quit -force-metal -buildTarget Android -projectPath "$PROJECT" \
  -executeMethod Oryn.Editor.OrynWorkspaceSetup.BuildAndroid \
  -logFile /private/tmp/oryn-workspace-build-final.log
```

Output: `Builds/Android/OrynWorkspace.apk`. The workspace scene is created only when
missing; later builds preserve scene content. The setup normalizes panel text sizing.
The visual layout preview is `Builds/Preview/Workspace.png`; it is not a headset capture.
Near-full Mac disk space remains a constraint for future builds.

## Verification and physical acceptance

### Current 1.6 generation receiver, 2026-09-26

- User confirmed 1.5 runtime loading, manipulation and resizing work. Controls are
  left unchanged; next priority is prompt-based asset generation, not multipart objects.
- Added an automatic, checksum-verified USB inbox and import receipts. The Mac console
  owns generation/API credentials; the headset only receives completed local GLBs.
- See [generation setup and verification](ORYN_GENERATION.md). Live provider generation
  requires an account/key and explicit per-job approval; the avocado delivery is a test,
  not generated output.

### Previous 1.5 resize repair / runtime model loading, 2026-09-26

- User reported that 1.4 made manipulation slightly better but resizing stopped working.
- Resize now has a separate bounded near-object acquisition path (15 cm) and uses raw
  pinch separation rather than projected surface anchors. Manipulation keeps contact
  acquisition. Rejected distant/deep-interior targets, fresh-pinch safety and tracking
  recovery rules remain in place. Mode transitions emit `ORYN_MODE` diagnostics.
- 350 interaction checks passed (284 workspace plus 66 legacy). New regression cases
  cover coincident corner anchors with separated pinches, acquisition without physical
  contact, enlarge/shrink, one-pinch waiting, and switching between manipulation/resize
  without changing pose or size unexpectedly, for all left/right input combinations.
- 10 additional checks loaded an actual external GLB, normalized its bounds, excluded
  cameras/lights, rejected missing/truncated/invalid files, and verified the fixture is
  outside compiled asset folders, and checked cancellation. Model and panel previews
  were visually inspected. Total: 360 automated checks.
- Final Android build succeeded in 33.6 seconds with editor exit 0; signature verified.
  APK SHA-256: `54757fe1f36cb82afa579f256531d45d7bb7ed5d6d91e64c5b8e666dd215ea65`.
  Build log: `/private/tmp/oryn-runtime-build-final.log`. M1 scene hash remains unchanged.
- Installed and launched successfully on Quest; device reports version 1.5/code 6.
  External avocado parsed and adopted into the workspace in 0.28 seconds on device.
- Headset gesture acceptance still requires user testing; automated input tests cannot
  establish the reliability of physical finger recognition.

### Previous 1.4 surface-contact update, 2026-09-26

- 310 automated checks passed: 244 workspace checks plus 66 earlier grab checks.
- New checks cover face/corner/interior queries, rotated/nonuniform boxes, spheres,
  swept contact, tracking-teleport rejection, grace-period acquisition/expiry, no
  closed-hand acquisition after recovery, visual finger convergence, bone lengths,
  and joint correction limits.
- Android build succeeded in 48.6 seconds with editor exit 0; APK signature verified.
- APK SHA-256: `7acfdc23702f7828cb9adf406dae61b121c1540bc92150d96f67b34b13cf29f4`.
- Quest installation returned `Success`, launch `Status: ok`; device package reports
  version 1.4 / code 5. Startup emitted the new `contact=surface_anchors_visual_fingers`
  readiness marker and created passthrough. No contact-script exception was observed
  in the startup check. Visual hand binding is deferred until valid hands are tracked;
  `ORYN_CONTACT_VISUAL_READY` was not present in that initial startup sample.
- Build log: `/private/tmp/oryn-contact-build.log`. Original M1 scene hash is unchanged.
- Physical contact quality, visual hand skinning, and gesture feel require a headset
  test. Mathematical checks do not prove absence of penetration or realistic grasping.

### Previous 1.3 gesture update, 2026-09-26

- 278 automated checks passed: 212 workspace/gesture checks plus 66 earlier grab checks.
- Build succeeded in 45.6 seconds, editor exit 0; APK signature verified; panel render inspected.
- SHA-256: `091d1ddddcdaf39b0cc0d6f85f430222360a35b831a56c2c7bf8e6aae786a1fd`.
- Quest installation returned `Success`; launch returned `Status: ok`.
- Runtime emitted `ORYN_M3_READY gestures=two_finger_resize_three_finger_manipulate`
  and created the passthrough feature. The existing nonfatal Unity `AssetPackManager`
  lookup message remained; no new gesture-script exception appeared in the startup check.
- Temporary build log: `/private/tmp/oryn-gesture-build.log`.
- Physical recognition of thumb-plus-two-fingertips and the feel of the new controls
  remain pending the user's headset test. Mathematical tests do not prove gesture recognition.
- Resizing uses two hands in this pass; one-hand pull-away resizing is not implemented.

### Previous 1.2 build and deployment, 2026-09-26

- 252 checks passed (186 new + 66 previous); scene validation passed.
- Final build succeeded in 15.8 seconds with editor exit code 0. APK signature verified.
- APK size: 54,209,002 bytes; SHA-256:
  `1a553bf40b29c7baa242acc592c23593047fcfca6fdfda3297c7422c34aa0de5`.
- Corrected panel render was visually inspected; labels fit their buttons and backing.
- Quest installation returned `Success`; launch returned `Status: ok`.
- Device log emitted `ORYN_M3_READY` and created the passthrough feature.
- The existing Unity Android `AssetPackManager` class lookup message recurred during
  startup; app initialization continued. No new workspace script exception or fatal
  crash was observed in the startup check. Physical gestures still need user testing.
- The original M1 scene hash remained unchanged. M2 is retained as its own scene.
- Temporary log: `/private/tmp/oryn-workspace-build-final.log`.
- Mac free space fluctuated between 1.3 and 2.0 GB; larger builds need more space.

### Acceptance checklist

Automated tests now cover 284 transform/gesture/contact/latch checks and 66 previous grab checks:
translation, rotation, scaling limits, both release orders, rejoining, same-side and
third-source rejection, degenerate spans, independent objects, loss of ownership,
reset, input activation/recovery, gesture classification, isolated resizing, size-locked
manipulation, mode transitions, opposing wrist rolls, and rotation speed limits.
Scene checks validate input refs, prefabs,
colliders, buttons, font, and passthrough. The rendered panel is visually inspected.

Hardware acceptance remains pending the user's test:

0. Approach a face, edge, and corner with an open hand. Check the mint contact highlight
   and surface marker, then close thumb + two fingertips to hold. Check both hands and
   the sphere. Light penetration should receive a small visual correction without
   stretched fingers. Release and move away: the visual hand should follow tracking
   normally. Check controller grip-marker surface acquisition as well.
1. Create a cube and sphere with each input mode; holding a button must not repeat.
2. Hold with both controller side grips or three-finger hand grips. Move/rotate and
   spread the hands: size must remain unchanged. Release either hand and continue.
3. Use thumb/index pinches in both hands (or both controller index triggers), pull
   apart/together, and verify only size changes. One pinch must wait rather than drag.
4. Change between two- and three-finger gestures without a size, position, or rotation
   jump. Mixed gestures and uncertain tracking must pause rather than resize.
5. Hold a separate object in each hand and move them independently.
6. Check selection labels, Reset Selected, B/Y recenter, and Delete confirmation.
7. Lose one hand's tracking, then both; verify no stuck ownership or object jump.
8. Check the session-only limit: restarting begins a fresh workspace, not a saved layout.

Do not claim the physical two-handed experience is verified from mathematical tests alone.
