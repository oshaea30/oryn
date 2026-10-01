# Executable connections 003 — measured result

**The placement/repair mechanism works on a limited example; general request
fulfillment is still unproven.** [Protocol](CONNECTION_EXPERIMENT.md),
[records and hashes](results/connections-003.json). Live execution was frozen at
`67f7d80`. Sol high generated all object-specific geometry and requirements; no
Astra, GPU rental, manual output repair or ambiguous-delivery retry was used.

| Case | Observed result | Time |
|---|---|---:|
| Drone | 19 parts; four disconnected motor components corrected automatically; declared checks pass after repair | 118.20 s first render; 164.68 s revised render |
| Speaker | Response incomplete at 12,288 output tokens; no geometry retained | 159.49 s case elapsed |
| Leaf/seed lamp | 5 parts; declared checks pass, but request coverage fails | 98.38 s render ready |
| Known sharpener | Response incomplete at 12,288 output tokens; no geometry retained | 133.33 s case elapsed |

Exact JBL remained evidence-blocked. Role plans were replayed. The original 30/120
second targets remain unmet for the repaired drone; the lamp's timing does not
count as useful-object latency because it missed the requested spatial relationship.
The speaker and sharpener consumed respectively 10,438 and 9,528 reasoning tokens
within their 12,288-token total output allowances. These are token-limit outcomes,
not timeout or geometry-quality failures. No automatic retry or token increase.

## What changed and what the evidence establishes

The model referenced actual form features; the executor derived connection frames
and computed nonroot poses from them. Ports were checked against the final boolean
solids, and all component pairs were checked for static interference. The drone
retained its 19 IDs/roles and original locked relations through correction. Its
four disconnected motor solids became connected without deleting a failed test.
The solver did not require per-object coordinates from Codex.

The completed drone and lamp proposals used only face mates: 18 and 4 respectively.
Coaxial placement, bore verification, radial fit and engagement are demonstrated by
synthetic positive/negative engine tests, not by these live model outputs.

The drone remains crude technical geometry with simplified propellers and electronics.
Its declared relationships passing does not prove detailed role fidelity, mechanics,
visual polish or product readiness. Connection compilation took roughly 0.015–0.035 s;
combined build/validation roughly 0.032–0.071 s. The latter includes a repeated
connection compilation, and is not a pure geometry-execution measurement.

The lamp exposes a distinct planning failure. Its request specifies a glowing seed
suspended **inside** a curled leaf. The output puts the seed outside a solid leaf-like
piece; its requirement contract contains no containment relation. Locking that
incomplete contract prevents later weakening but cannot recover the omitted intent.
No special-case seed position or containment rule was injected. This is a request
failure despite every declared check passing. Glow remains unsupported by the
inspection renderer and was not scored as a geometric defect.

## Precision audit after the frozen run

An independent submillimetre negative fixture exposed an absolute-volume tolerance
that could accept a completely removed small face patch. After the batch completed,
face/bore checks were changed to use probe-relative tolerance with a much smaller
numerical floor; collision tolerance was also bounded by component volume. Equivalent
numeric requirement values such as 0 and 0.0 no longer trigger a false lock rejection.
No live call used those post-run changes.

All three saved meshes were recompiled and checked under the stricter tolerances.
Every component's vertices, triangles and metadata remained exactly identical.
Verdicts stayed unchanged: initial drone fails; corrected drone and lamp pass their
declared checks. Original reports remain alongside separately labeled precision
audits. This does not cure the lamp's missing requirement or certify engineering fit.

Forty-five targeted Python tests pass. Three browser outputs load, select, separate
and reset, preserve selection through the drone revision switch, and keep unsupported
motion disabled. An offline pair inspector provides larger views of each declared
connection without changing either part's original geometry or assembly pose.
No Quest performance or interaction acceptance was performed.

## Cost and decision

Calculated API cost: **$0.578555**, below the $0.90 batch cap; no new uncertain
reservation. Provider invoiced cost is unknown. Prior uncertain reservations are
unchanged. Raw requests/responses, meshes and pair views remain under local
`Builds/NativeObjects/connections-run-003`; selected evidence is retained in this repo.

Stop this batch at its bounds. Do not describe the representation or generator as
solved, or run an unfamiliar-case success test while the known lamp still misses an
explicit request. The next investment decision has two concrete inputs:

1. Requirements must be checked against the original request **before** geometry
   construction/repair can be trusted to satisfy them. Current role coverage and
   locked connections do not constitute that semantic coverage check.
2. Two responses ran out of their reasoning-plus-output allowance. Future delivery
   experiments must distinguish that limit from bad geometry, preserve billing and
   latency, and avoid silently increasing budgets or replaying completed requests.

Retain the working general solver. A different model, larger geometry vocabulary
or extra format layer is not yet established as the solution to these two failures.
No additional paid calls, product integration or per-output repair followed this run.
