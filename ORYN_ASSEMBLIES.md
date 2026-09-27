# ORYN 1.8: prayer-to-spread and part interaction

This milestone uses the locally separated 39-island drone. It adds runtime interaction
wrappers to multi-mesh GLBs, not semantic understanding. The original one-mesh drone
and avocado remain unchanged. No new generation or texturing API calls are needed.

## Headset walkthrough

1. Grab the new **39-part model** to select it. It starts in whole-object mode.
2. Use the prayer-to-spread gesture below, or activate **EXPLODE** on the panel,
   to spread the pieces and enter parts mode.
3. Touch a piece and use the existing three-finger gesture (thumb plus two fingertips),
   or a controller side grip, to move/rotate it. Each hand can hold a different piece.
4. **ISOLATE / ALL** hides the other pieces; activate it again to show them.
5. **ASSEMBLE** restores every piece's original position, orientation and size, shows
   everything, and returns to whole-object mode.

**PARTS / WHOLE** enters parts mode without exploding, or reassembles and exits it.
**RESET SELECTED** restores an individual piece to its assembly-relative home; for a
whole assembly it reassembles first, then restores the original whole-object size and
places it within reach. As of 1.9.1, B/Y only recenters the menu; it does not reset parts.

Two-hand pinch resizing uses the existing state machine without gesture/math changes.
It can resize an individual part in parts mode or the full model in whole-object mode.
The known pinch-feel regression is not claimed fixed in this milestone.

## Prayer-to-spread (1.8)

The user subsequently confirmed the gesture works very well on the headset as a
first iteration. ORYN 1.9 leaves its behavior unchanged and adds the
[persistent part inspector](ORYN_KNOWLEDGE.md).

Release anything held. Near the drone, hold open hands with palms facing each other
and fingers pointing upward for about a third of a second. Leave a 5–10 cm gap
between palms so Quest can track both hands; contact is not required. The panel
shows the arming prompt, then a spread percentage. Move hands apart to spread the
parts, or together to bring them back. Maximum spread is reached at 65 cm separation.
Turn palms away or curl a hand to leave the parts at the current spread.

- This controls part spacing only, not object scale. Maximum spacing is the same
  bounded 2.1× home-position offset as the EXPLODE button.
- A selected assembly is used; without one selected, exactly one multipart object
  must be nearby. The palm midpoint must stay within 85 cm of the assembly root.
- Arming requires palm separation at most 16 cm for 0.28 seconds. Fingers must be
  extended and palms facing inward. Pinching, holding an object, loading a model,
  poor tracking, or lost application focus prevents engagement.
- Every fresh prayer starts from the assembled layout, restoring hidden pieces and
  any manually moved/resized parts. Closing the spread fully and ending the gesture
  returns to whole-object mode. Ending at a nonzero spread leaves parts mode active.
- Tracking loss freezes the spread and requires a fresh prayer to resume. Button
  presses and object grabs are suppressed during arming/spreading. Existing pinch
  classification and resize math are unchanged.
- This gesture is for tracked bare hands. Existing panel controls remain available
  for controllers. Headset gesture feel still requires physical user testing.

### 1.8 verification

- Unity checks: 298 assembly (actual 39-part drone), 31 prayer recognizer, 284
  workspace, 66 legacy, and 15 runtime/manifest: **694 passed**.
- Tests cover continuous/bounded spread, unchanged scale, restoring home transforms,
  short-dwell rejection, palm orientation, handedness, pinch exclusion, tracking loss,
  fresh rearming, invalid samples, and stalled-frame protection.
- Python generation/inspection regressions: **46 passed**.
- Panel preview rendered and visually inspected; prayer instructions fit below buttons.
- Android build succeeded in 52.82 seconds with Unity exit 0. Log:
  `/private/tmp/oryn-prayer-build.log`.
- APK signature verified; version 1.8 / code 9 installed with existing app data retained
  and launched successfully on the connected Quest.
- APK SHA-256: `fa190d52c9256f5dd37f3fe5c3970745a1a5f3e93685d951de0ee8888d0e5547`.
- Existing drone resent, with no paid API calls. Delivery receipt state is recorded in
  `.oryn-generation/194f107aee2550dd9369453ad3fe6bb8/island-analysis/quest-assembly-delivery-v1.8.json`.

## Ownership and interaction boundaries

- `OrynAssembly` owns up to 64 part interaction wrappers per imported assembly. One
  mesh renderer becomes one part. Models with one renderer or more than 64 retain
  whole-object interaction. No assumptions are made about Meshy-specific names.
- The workspace's 12-object limit counts assemblies, not their internal parts.
- Only whole-object OR visible-part targets are eligible at a time. The root collider
  is disabled in parts mode, avoiding the root intercepting all part grabs.
- Part colliders are oriented bounding boxes, not precise triangle-surface colliders.
  Very small dimensions have a bounded minimum thickness. Exploding helps separate
  overlapping hit targets; assembled part picking may still be awkward.
- Part origins are centered on their geometry bounds. Original renderer world poses
  are preserved when wrappers are created; mesh resources remain owned by glTFast's
  importer component underneath the assembly root.
- Parts share resource lifetime with the parent. Part deletion is intentionally
  disabled; deleting the full object retains the existing confirmation gate.
- Mode changes, reset, isolation and reassembly release affected holds and contact
  latches. Tracking/focus loss releases all part states. Re-entering parts mode rebases
  world-space interaction state after whole-object movement/resizing.
- Reassembly restores cached local transforms rather than guessing geometric matches.
  It does not mean arbitrary removed/replacement components can be mechanically fitted.
- Session layouts are still not saved across application restarts. Installing this
  update restarts the app; delivered source files and receipt history remain stored.

## Previous 1.7 verification

- 215 new Unity checks against the actual 39-part drone: ownership, target exclusivity,
  independent left/right parts, pose isolation, hide/show, explode transforms,
  position/rotation restoration, owner movement rebasing, original resize behavior,
  part-size reset, idempotent reassembly, and preservation of imported mesh resources.
- Existing checks: 284 workspace + 66 legacy + 15 runtime/manifest = 365.
- Combined Unity checks: 580. Python generation/inspection tests remain separate.
- The nine-button panel was rendered and visually inspected before deployment.
- First Android build ran out of disk space after passing tests. Removed only four
  verified regenerable build-cache directories: the prior objcopy staging directory,
  IL2CPP debug backup, and two generated Gradle build-output directories. No source,
  original/derived model, API key, unrelated project or existing APK was removed.
- Retry build log: `/private/tmp/oryn-assembly-build-retry.log`.
- Retry succeeded in 51.34 seconds with Unity exit 0. APK signature verified;
  version 1.7 / code 8 installed over the existing package with data retained, and
  launched successfully. Device package manager confirms version 1.7 / code 8.
- APK SHA-256: `10a301e08844281f6d78caa7e6b5a1e4fd8ee51034a3e0e8ddb8f0c04eb82b7f`.
- Python regressions: 46 tests passed.
- The existing derived 39-part GLB was sent using checksum validation and manifest-last
  transport, delivery `50c65659d5fa40a9afaee721c068e6de`. USB transfer completed;
  headset import acknowledgement was pending at handoff. Local record:
  `.oryn-generation/194f107aee2550dd9369453ad3fe6bb8/island-analysis/quest-assembly-delivery-v1.7.json`.

Build the same tests using `ORYN_ASSEMBLY_TEST_MODEL` pointed at the separated GLB and
`Oryn.Editor.OrynRuntimeModelTests.ValidateAndBuild`. Without the environment variable,
assembly tests use a synthetic three-mesh fixture. The actual-drone count assertion
requires this milestone's 39-part fixture when the variable is supplied.

Device gesture feel and the full explode/grab/isolate/reassemble walkthrough still
require user testing; editor tests do not substitute for that hardware check.
