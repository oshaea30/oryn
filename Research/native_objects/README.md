# ORYN native-object generation experiment

Research question: can a generator produce geometry, semantic components,
assembly relationships and usable motion for the same object, with no per-output
manual repair? This directory is a research harness, not an implemented generator
or replacement for ORYN's production object route. Answer development is paused.

## Minimum output and evaluation

The research package (`oryn-native-experiment-v1`) retains component-bound triangle
geometry, parent references, semantic roles/subsystems, motion definitions and
optional independently exported runtime samples. Geometry is baked in the stated
measurement frame. Source files remain unchanged. Each of geometry, semantics,
hierarchy and motion records an origin: authored, model generated, geometrically
decomposed or unknown. Repairs are an explicit list, never hidden in an adapter.

This is an initial interchange subset, not the final ORYN format. Fixed and rotary
motion are evaluated; slider-crank, materials, attachment interfaces and collision
sweeps need further evaluators. There is no new language-answering path.

Checks detect empty/all-degenerate parts, invalid indices, duplicate bindings,
broken references, cycles, non-unit axes and runtime motion inconsistent with a
rotation definition. Actual Unity mesh vertices at nine phases are compared to
an independent Rodrigues rotation calculation. The observed control error is about
7e-8 metres. This is a sampled check, not continuous collision/physical validation.

Semantic correctness, attachment fit, swept clearance, visual quality, physical
validity and Quest performance explicitly remain unassessed. A structurally valid
package cannot pass the native generation milestone; the goal flag stays false
until those missing evaluations and an actual generation have been established.
The viewer's explode/reset is a geometry inspection operation, not evidence that
a physically feasible disassembly path exists.

## Measured controls (2026-09-29)

- Authored runtime drone: 17 parts. Actual Unity geometry and motion exported by
  `OrynNativeObjectExport.Run`; all output facets authored. Motion agreement passes.
  This is a mechanics control, not a polished visual target or a learned result.
- Saved Meshy drone: 39 disconnected geometric pieces, 10,491 triangles. Source
  untouched; no semantic labels, hierarchy or motion inferred. Those facets remain
  missing. The analysis view uses source-local coordinates and neutral shading.
- Negative tests deliberately corrupt geometry, graph references and motion axes.
  An otherwise valid but wrong axis fails against independent runtime samples.

Neither control is evidence of native generation. No new inference or training
has run. No part has been moved or labeled to make a generated result pass.

Run from the repository root:

```sh
python3 -m unittest Research.native_objects.test_experiment -v
python3 -m Research.native_objects.experiment \
  --runtime Builds/NativeObjects/authored-drone-runtime.json \
  --saved-glb .oryn-generation/194f107aee2550dd9369453ad3fe6bb8/model.glb \
  --output Builds/NativeObjects/a-new-run
python3 -m http.server 8771 --bind 127.0.0.1 --directory Builds/NativeObjects/a-new-run
```

The Unity export is an editor-only command; it does not deploy to Quest. Open the
local report to orbit, separate, isolate and reset the same mesh data, and play
recorded motion only where it exists. Analysis shading is not a material-quality
assessment. The browser checker uses these controls without any generation calls.

## Selected geometry baseline

[PartCrafter](https://github.com/wgsxm/PartCrafter) is selected for a first geometry
experiment: image-conditioned multiple-part output with released code/weights.
The released script caps requested part count at 16; part count is supplied, not
predicted in this run. It does not output the required semantic/joint/behavior
records. Published inference requires a CUDA GPU (at least 8 GB). This Mac's Apple
GPU cannot run the documented CUDA path. Thirteen parts at 1,024 tokens each is
not assumed to fit the minimum memory; propose a 48 GB worker and retain OOM as a
failed result. Reference: [upstream inference](https://github.com/wgsxm/PartCrafter/blob/3d773bf02fad51c7ab31a5615573fec93b287b30/scripts/inference_partcrafter.py).

Pinned code: `3d773bf02fad51c7ab31a5615573fec93b287b30`.
Pinned model: `wgsxm/PartCrafter@69a0ffc1dad5e48e7e5ed91c0609f2b1276eb31f`.
Both upstream code and model card declare MIT; this is not a blanket clearance
of all dependencies or training assets for commercial deployment.

The minimal entry adapter calls the upstream pipeline with its default object
settings. Unlike the upstream CLI, it does not load BRIA background-removal weights,
request Gemini assistance, render through OpenGL or substitute dummy meshes for
decoder failures. It uses an already prepared reference image. Missing/empty
parts fail the run; all-degenerate output fails the separate evaluator.

`run_partcrafter.py` prints a plan by default. Execution requires `--execute`, a
clean pinned checkout, CUDA, previously downloaded and hashed pinned weights and
a new output directory. It journals before inference, enforces a 30-minute process
timeout, records environment/adapter/weight/input/output hashes and never retries.
The timeout does not terminate a cloud rental or impose an account billing cap.
GPU results remain untested until a real worker is available.

## Proposed first run — no rental started

Input: a neutral-background render of our saved generated drone, derived locally
without changing geometry. Record its source checksum, image checksum and camera
choice. It is a baseline reference, not a polished target, ground truth internals,
or a withheld user design. Supply 13 parts (coarse experimental budget, not a
verified anatomical count), seed 0, 50 steps, 1,024 tokens per part. Freeze these
before running. One attempt; failures count. No automatic retries or paid APIs.

This first test asks whether the model produces more useful separated geometry
from that view. It cannot prove arbitrary prompt generation, hidden internals,
correct articulation or visual improvement across varied designs. After this
smoke test, use independently chosen references and multiple predeclared seeds;
do not train or tune on the evaluation set. A learned articulation baseline is a
separate subsequent comparison, not a property to attach by hand to this output.

Proposed worker: NVIDIA A40 48 GB, Linux, Python 3.11, CUDA 12.4/PyTorch 2.5.1.
[Runpod pricing](https://www.runpod.io/pricing), checked 2026-09-29, lists A40 Pods
at $0.49/hour. Two hours would be $0.98 GPU time before storage, taxes or other
charges. Treat this as an estimate, not a reserved quote or total-spend guarantee.
Propose a $5 maximum authorized spend and two-hour rental window including setup;
confirm actual instance/storage rates and a termination mechanism before launch.
A funded account/connection and user approval are still needed. No provisioning,
account creation, download of weights or paid run has occurred.

Only the research adapter, reference image and public model/code belong on the
worker. Production keys, object library, application journals and headset data
are not required. Download results and terminate the worker/storage after the run.

Preparation on an approved worker (not executed here):

```sh
git clone https://github.com/wgsxm/PartCrafter.git /workspace/PartCrafter
git -C /workspace/PartCrafter checkout 3d773bf02fad51c7ab31a5615573fec93b287b30
# In a dedicated Python 3.11 environment:
python -m pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124
python -m pip install torch-cluster -f https://data.pyg.org/whl/torch-2.5.1+cu124.html
python -m pip install -r /workspace/PartCrafter/settings/requirements.txt
# From the isolated ORYN research copy:
python -m Research.native_objects.prepare_weights --repo /workspace/PartCrafter --download
python -m Research.native_objects.run_partcrafter \
  --repo /workspace/PartCrafter --image /workspace/drone-reference.png \
  --output /workspace/oryn-run-001 --parts 13 --seed 0
# Review the plan, then invoke the same command with --execute.
# Download the run directory and evaluate on the Mac:
python3 -m Research.native_objects.experiment --partcrafter /path/to/oryn-run-001 --output Builds/NativeObjects/generated-run-001
```

The installed dependency versions must be recorded on the worker; upstream's
requirements are not fully locked. Environment setup and VRAM usage still need a
real-worker test, so successful execution is not promised.

## Articulation comparison

[PhysX-Anything](https://github.com/ziangcao0312/PhysX-Anything) at
`e221826e6176d940905126d1894f9c1c933b70a8` exposes a staged VLM/geometry/URDF workflow.
It is relevant to structure plus articulation, but has not been run or adapted.
Its [S-Lab license](https://github.com/ziangcao0312/PhysX-Anything/blob/e221826e6176d940905126d1894f9c1c933b70a8/LICENSE)
restricts use to non-commercial purposes without additional permission. Keep it a
research candidate rather than adopting it into the product. No conclusion about
its drone quality, internals, fit or Quest compatibility has been established.

Next decision: examine the actual generated parts, preserve failures, and decide
whether the principal gap is geometry, semantic structure or articulation. Do not
spend weeks polishing a configurator or start training before that evidence exists.
