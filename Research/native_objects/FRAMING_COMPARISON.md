# PartCrafter framing comparison 001

Frozen before run B on 2026-09-30. Protocol and input hashes:
[framing-protocol-001.json](results/framing-protocol-001.json).

Question: does foreground framing materially improve this configuration's visual
coherence AND component usefulness? This is one paired seed, not repeatability or
an estimate of the model's ceiling. No output repair, semantic authoring, animation,
style transfer, new view, learned background removal or additional seed in this run.

## Preprocessing audit

Pinned upstream [inference entry](https://github.com/wgsxm/PartCrafter/blob/3d773bf02fad51c7ab31a5615573fec93b287b30/scripts/inference_partcrafter.py)
passes the loaded image directly unless `--rmbg` is supplied. The optional
[prepare_image path](https://github.com/wgsxm/PartCrafter/blob/3d773bf02fad51c7ab31a5615573fec93b287b30/src/utils/image_utils.py)
finds foreground, crops it, and adds approximately 10% longest-side padding on each
side. Our RGB adapter intentionally bypassed that path, so the encoder received
all the original white margin. The image encoder's
[pinned configuration](https://huggingface.co/wgsxm/PartCrafter/blob/69a0ffc1dad5e48e7e5ed91c0609f2b1276eb31f/feature_extractor_dinov2/preprocessor_config.json)
resizes the short edge to 256, then center-crops to 224 and normalizes RGB.
The pipeline invokes this processor for each supplied image. No multi-view fusion
is introduced: upstream repeats the same image for the requested parts.

A's visible foreground bounds are 310 x 199 pixels within 1024 x 1024. B crops
those bounds, centers them on a 372 x 372 white square, and resizes to 1024 x 1024.
This gives approximately 83% foreground width before encoder cropping, versus
30% for A. Deterministic foreground detection is valid for this known white render,
not a general photograph segmenter. Source pixels are resampled, not synthesized.
The exact preparation code and Pillow version are retained with the protocol.

Freeze code, weights, adapter, 13 requested parts, seed 0, 50 steps, 1,024 tokens
per part, guidance 7, float16, A40 GPU, and Run A's installed Python packages.
Record host driver differences and numerical nondeterminism as limitations.
Require identical input/adapter/weight checksums and package-version comparison
before accepting B as a controlled result. Input checksum intentionally differs.

## Scorecard fixed before B

Qualitative desktop inspection uses assembled front, side and oblique views,
exploded view, and each of the 13 isolated meshes for both conditions. Preserve
screenshots and explain every score. Scores are reviewer judgments, not automatic
semantic verification. Use 0 = fail, 1 = partial, 2 = pass; not tested is separate.

| Criterion | Fail (0) | Partial (1) | Pass (2) |
|---|---|---|---|
| V1: assembled identity | Drone not recognizable | Recognizable body but missing/distorted major rotor positions | Coherent body and four recognizable rotor positions |
| V2: detached debris | Multiple substantial stray fragments or a detached major assembly | Small stray fragments, no detached major assembly | No obvious stray fragments in the prescribed views |
| V3: major geometry | Multiple major shapes severely malformed | Local defects but most major shapes readable | No obvious severe defects in body, arms and propeller shapes |
| P1: complete major pieces | Fewer than three complete useful major components | At least three complete useful components, others incomplete/fused | Body, arms and four rotor units are complete enough to inspect |
| P2: useful independent selection | Fewer than three useful components selectable separately | At least three, but some important components fused | Body/arms and each propeller selectable without unrelated major geometry |
| P3: useful boundaries | Mostly fragments or one mesh absorbs most useful components | Some meaningful boundaries, some fusion/fragmentation | Major boundaries visually correspond to components; propellers distinct from motor housings |
| P4: assembled placement | Multiple major pieces detached or visibly misplaced | Most pieces positioned sensibly, local mismatch remains | Major pieces align coherently in assembly |

A substantial stray fragment has a visible span roughly 5% or more of the central
body's longest dimension; a major rotor/body/arm counts regardless of this size.
Do not mistake an intentionally separated view for an assembly defect. A smooth
surface alone does not earn component points. Visual alignment is not mechanical
fit, an attachment interface, or proof of hidden internals.

Report separately: structural validity; triangle/component/material counts where
measurable; desktop loading/explode/isolate/reset; runtime import, draw calls,
texture memory, colliders, load time, frame time and memory on Quest. All Quest
items stay **not tested** unless measured on the headset. No triangle-only FPS
prediction. Zero per-output repairs is a hard gate, not a weighted score.

## Decision rule

Material improvement requires BOTH V-total and P-total to improve by at least two
points over A, no V criterion at zero, and P1/P2 at least one (three useful complete,
selectable components). Execution must be comparable and original meshes untouched.
A desktop quality pass requires all V and P criteria at two; it is still not Quest
acceptance or the native-object milestone.

- If material improvement passes: preserve B and propose a separately recorded
  repeatability check with seeds 1 and 2 and the same reference/settings. Do not
  automatically buy those runs or promote B to the product.
- Otherwise: stop paid trials of this configuration. Record the failure and assess
  the next candidate against these needs before spending again. Do not infer that
  custom training is warranted or that all PartCrafter configurations fail.
- If setup/inference fails or fixed variables cannot be matched: classify the
  comparison as inconclusive, preserve logs, terminate the rental, and do not retry.

Budget: total A+B stays within the existing $5 ceiling; B is one A40 rental at no
more than $0.49/hour compute, 80 GB temporary disk, two-hour local cleanup deadline.
The tested explicit-delete watchdog depends on the awake Mac and network; it is
not a provider billing cap. Download and verify outputs, terminate early, and
verify no experiment resources remain before local evaluation.
