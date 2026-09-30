# Framing comparison 001 — completed 2026-09-30

**Tighter framing improves recognizability, but fails the predeclared improvement
gate. Stop paid trials of this configuration.** No extra seeds or Quest promotion.

The [protocol](FRAMING_COMPARISON.md) and input hashes were committed at `0a2e466`
before B. [Machine-readable evidence](results/framing-comparison-001.json) retains
both reviews, exact output hashes, static preflight, settings and cleanup estimates.

| Criterion | A: original framing | B: tighter framing |
|---|---:|---:|
| Assembled identity | 1 | 2 |
| Detached debris | 0 | 0 |
| Major geometry | 0 | 0 |
| **Visual total / 6** | **1** | **2** |
| Complete major pieces | 1 | 1 |
| Useful independent selection | 1 | 1 |
| Useful boundaries | 0 | 0 |
| Assembled placement | 0 | 1 |
| **Component total / 8** | **2** | **3** |

0 = fail, 1 = partial, 2 = pass. B gains one point in each category; the rule
required at least two in each, no visual zero, at least three useful selectable
components, comparable execution and zero repairs. It fails the first three gates.
The density issue below is reported separately, not a new visual scoring criterion.

## What changed visually

B shows a recognizable body and four rotor positions, with more sensible assembly
placement. However, substantial blade-like debris remains above the body, several
propellers are incomplete or malformed, and part_09 fuses the body, arms, camera
and several end housings. Part_04 combines gear-like structures and end housings.
Thirteen files still do not constitute thirteen useful components.

P1/P2 receive conservative partial credit for B's compact part_00, body-like part_09
and main propeller shape in part_06. Other meshes contain slivers and fragments;
these descriptions are observations, not verified semantic labels. Every score's
reason is preserved in the result JSON. Both conditions use four assembled views,
one exploded view, and front/oblique views of all 13 isolated meshes. Isolated
views auto-frame; no geometry changes. This is one agent's qualitative desktop
review, not independent blinded scoring.

[Original framing: all views](results/framing-001/a-contact-sheet.png) ·
[Tighter framing: all views](results/framing-001/b-contact-sheet.png)

## Execution and runtime evidence

- One B inference: 211.582 seconds, 13 meshes, no retries or manual repairs.
- Code, weights, adapter, package versions, A40, seed 0 and generation settings
  matched A. Only input framing intentionally changed. Provider-reported host CUDA
  capability differed (13.2 vs 13.0), with identical CUDA 12.4 container runtime;
  this and numerical nondeterminism limit causal attribution.
- B has 1,090,246 triangles versus A's 195,708: about 5.57 times as many.
  B totals 545,533 vertices, 19,639,500 GLB bytes, 13 primitives, no declared
  materials/textures/images. These counts are not Quest performance measurements.
- Default inspection rejected part_09: 271,462 vertices exceeds the unchanged
  200,000-vertex static limit. An explicit offline research option enabled visual
  review while retaining the failure. Other validation stayed enabled; no decimation.
- Desktop loading, separation, isolation and reset worked; motion stayed unavailable.
  Reset restored control/camera state; exact canvas pixels varied slightly on redraw
  (mean RGBA delta A 0.205/255, B 0.508/255), so pixel-exact rendering is not claimed.
  All 13 source hashes match the worker journal. Quest import, manipulation, draw
  calls, memory, colliders, loading and frame time remain **not tested**.
- No semantic relationships, hierarchy or motion were generated. Structurally valid
  triangle data does not establish mechanical fit or native-object success.

## Cost and disposition

B's rental lasted about 9.23 minutes: estimated $0.0771 including temporary disk.
A+B is approximately $0.1541, within the existing $5 ceiling. Billing API records
were still pending; these are estimates. B's pod was explicitly terminated after
verified download; follow-up checks showed no pods or network volumes.

Raw output, logs, frozen dependencies and local evidence are preserved under
`Builds/NativeObjects/partcrafter-framing-b-001` and
`Builds/NativeObjects/framing-comparison-001` (large local files are Git-ignored).
The comparison page is `index.html` in the latter; serve that folder locally.
The committed scorecard, hashes and contact sheets remain reviewable without it.

Next: assess an alternative approach for coherent geometry and useful component
boundaries before spending again. Do not infer that custom training is necessary
or that every PartCrafter configuration fails. Answering, voice, motion inference,
new provider integrations and the Quest product stay paused/stable as agreed.
