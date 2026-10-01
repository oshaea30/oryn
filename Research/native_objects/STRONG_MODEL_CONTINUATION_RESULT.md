# Strong-model 014–015 — drone repair succeeds; speaker intent still blocks

**The completed stronger-configuration comparison produces a structurally passing
drone and fan row with no manual geometry edits. The speaker remains blocked before
geometry.** This establishes a useful capability improvement on the drone, not a
reliable general generator or a polished finished-object pass.

015 was frozen at `336d11e`, continuing [014](STRONG_MODEL_RESULT.md) after the user
confirmed a $10 API reload. The geometry executor, requirements/repair gates and
acceptance tolerances stay unchanged. All frozen hashes match. The failed funding job
and its hold remain intact; the continuation reuses the exact saved drone and fan plans.
There is no additional starting plan, seed, repair cycle, model judge or GPU job.

## Results

| Case | Sol medium baseline | Astra xhigh result |
|---|---|---|
| Drone | Fresh plan fails global orientation; one local patch still fails and regresses symmetry. | Fresh plan passes global arrangement but fails four local feature/mate checks. Its one model-authored patch corrects three form rotations on the controller shape. **292/292 checks pass**, all **308** previously passing facts preserved, zero regressions. |
| Fan row | One patch passes 55 checks, preserving 55 facts. | One patch also passes **55/55 checks**, preserves **55** facts, zero regressions. Five blades per rotor retained; Sol's patch used four, which was permitted. No added success on the existing acceptance gate. |
| Speaker | Valid inventory; front-face placement lacks an executable spatial rule. | Valid 18-record inventory includes front-face contact and driver arrangement rules, but inferred mandatory rear-cover placement `r15` has no executable rule. **No geometry**, rather than silently omitting it. |

The drone patch changes only three rotations in `controller_shape`; no port bindings,
logical mates, parts or constraints change. Fourteen out-of-scope components remain
unchanged, including frame, arms, motors, propellers and battery. The permitted ESC
shapes are also left unchanged. All geometry and preserved facts are revalidated.

The fan patch changes two shared shapes and six feature selectors. Its panel stays
unchanged. The five-blade layout is preserved while the feature exposure/axis checks
are corrected. As in the earlier Sol result, visible center supports/bearings are
missing: passing coaxial checks is not evidence of complete working fan mechanics.

## Visual and interpretation limits

Both generated assemblies are recognizable and support independent part selection,
explosion, isolation and reset in the desktop viewer. They remain simplified technical
models, with basic materials and incomplete engineering detail. Structural acceptance
passes; visual quality is partial. No motion, physical operation or Quest performance
is established. Supplied component-role catalogs remain an experimental limitation;
this has not demonstrated autonomous discovery of components for arbitrary requests.

For the speaker, the limited predeclared interpretation assertions pass, including the
front-face binding. This does **not** override the full admission gate. `e3` (rear cover)
is a design-choice entity, while its inferred rear placement `r15` is marked required
without a registered spatial rule. It blocks construction. Relationships involving
optional components need consistent obligations and executable bindings before a plan
is built. Do not hand-label this one relation or silently discard the requirement.
Also retain the distinction between front-surface contact and a driver embedded in a
panel; the passing limited assertion alone does not establish that semantic distinction.

## Cost and latency

All four completed Astra calls use xhigh and a 32,768 output allowance. None hits its
output cap or 900-second deadline. Request time includes queue, network and polling.

| Completed operation | Request time | Input | Output (reasoning) | Conservative estimate |
|---|---:|---:|---:|---:|
| 014 drone plan | 367.60 s | 7,072 | 18,875 (11,376) | $1.0321500 |
| 015 drone patch | 61.24 s | 20,099 | 2,200 (1,445) | $0.3612375 |
| 015 speaker extraction | 163.31 s | 3,912 | 6,578 (4,954) | $0.3778000 |
| 015 fan patch | 217.15 s | 13,371 | 8,470 (7,396) | $0.5906375 |
| **Completed comparison total** | **809.31 s across calls** | | | **$2.3618250** |

New spending after reload is estimated **$1.329675**, below the $7.50 continuation
ceiling and its $7.4304875 complete worst-case preflight. No new uncertain holds or
funding errors. These are usage-derived estimates, not provider invoice amounts.
The old $1.8896375 funding-failure hold remains untouched; 014+015 accounting including
that hold is $4.2514625. Shared local remaining allowance is $7.4802025, not an account
balance. Use **$8.73** as conservative prior research allowance for subsequent budgeting,
including earlier runs and all holds. Daily and aggregate ceilings remain $15.

The drone needs about **7.15 minutes** for its plan plus repair. The fan takes longer
and costs more than Sol for the same structural pass. More capacity helps on this drone
sample; it does not establish a latency improvement or a universal benefit from xhigh.
Because model, reasoning effort and output allowance changed together, do not attribute
the improvement solely to one setting or to budget. Drone repair starting plans differ;
fan repair does use the exact same starting plan and request as Sol.

## Decision

Use this stronger configuration as the research capability reference while checking
unrelated object families. This result does not justify a drone-specific layout rule or
an immediate pose-solver expansion to overcome the former drone failure. The unchanged
executor can produce and validate one coherent 19-part assembly after automatic repair.

The next generic failure to isolate is the speaker's obligation/spatial-binding gap:
keep explicit user requirements, distinguish optional design details and their dependent
relations, and require complete executable spatial bindings or an explicit unsupported
result before geometry. Test that boundary across unrelated requests. Do not change the
frozen speaker result or weaken its meaning to obtain a pass. No further paid run was
dispatched after this comparison; no product promotion, animation or answer work began.

## Verification and evidence

42 targeted tests pass for request recovery, budget limits, unchanged prompts and runner
resumption. Thirty-six browser checks pass across both baselines and both repaired
candidates, with no page errors. All generated packages are unchanged by inspection.
The operator review reopens only the verified funding stop and leaves its full ledger
row unchanged; repeated review is idempotent and a later halt requires new review.

- [Repaired drone](http://127.0.0.1:8775/strong-model-run-015/?case=generic-drone-plan-1)
- [Repaired fan row](http://127.0.0.1:8775/strong-model-run-015/?case=cooling-fan-row-plan-1)
- [Frozen continuation](STRONG_MODEL_CONTINUATION.md)
- [Result audit](results/strong-model-015/post-run-audit.json)
- [Visual review](results/strong-model-015/visual-review.json)
- [Funding review](results/strong-model-015/funding-review.json)
