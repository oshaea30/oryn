# Object planning experiment 001

Question: can one application-owned planning policy interpret different requests,
choose useful component detail, and distinguish proposed designs from exact-product
claims before any geometry is generated?

This supports the existing coherent-object generation milestone. It does not
replace its geometry scorecard or introduce a new object format. Product/Quest,
answering, motion, Jev integration and further GPU runs remain outside this test.

## Frozen protocol

[Four requests and review criteria](planning_cases_001.json) cover a generic drone,
generic portable speaker, exact JBL Flip 7 internal assembly, and creative leaf/seed
lamp. All calls use the same instructions and output contract. Review criteria
are saved for assessment but never sent to the model. No source snapshots are
supplied: this tests whether missing evidence is recognized, not whether retrieval
works. The adapter can accept existing bounded source snapshots later.

The application constructs the request, invokes the model, validates the result
and records spending. There are no hardcoded object recipes, answer fallbacks,
per-case prompt changes, web tools or generation calls. A model chooses the
fidelity category; structural validation cannot prove that choice is correct.
Source ID membership cannot establish that a source supports a claim.

Plans contain intent, fidelity, detail depth, proposed component roles, assumptions,
unknowns and a next step. Generic/creative designs may propose geometry; exact
products remain blocked pending matching evidence and independent assessment.
Every result in this experiment has generation/execution disabled. Component
names are planned roles, not existing mesh identities or certified internals.

## Spending and execution

Default is an offline preview; it does not load credentials. Explicit execution
uses the saved ORYN research connection and existing persistent usage ledger.
The planning profile uses gpt-6-sol, medium reasoning, at most 2,048 output tokens,
with exact input counting and reservation before each generation call. Four calls
maximum, $0.05 per case, $0.20 batch ceiling; existing $2/day and per-investigation
limits also apply. No automatic retries, budget resets or model escalation.
Timeouts retain reservations; incompatible usage/model responses halt paid work.
Costs calculated from tokens are estimates, not confirmed invoices.

```sh
python3 -m Research.native_objects.planning_experiment --output Builds/NativeObjects/planning-preview-001
python3 -m Research.native_objects.planning_experiment --output Builds/NativeObjects/planning-run-001 --execute
PYTHONPATH=Orchestrator python3 -m unittest Orchestrator.test_object_planning Orchestrator.test_research_providers Orchestrator.test_spending
```

Output directories must be new. Operation IDs bind protocol and request body;
attempted paid operations cannot be replayed against the shared ledger. Freeze
this protocol in Git before live execution, retain all outcomes and review them
together. Do not repair individual responses or retry weak cases.

## Decision rule

Pass requires all four cases to meet their predeclared criteria without fabricated
evidence or per-object intervention. Honest incomplete/poorly scoped plans are
partial; invented exact facts or ignored intent fail. Invalid/incomplete model
responses or setup/budget failures leave the batch inconclusive. Offline tests
establish validator/ledger behavior only, not model quality.

Even a four-case pass is a small feasibility result. Before any generalized claim,
use a separately frozen unseen-object/repeated-run evaluation. Before generation
integration, test whether a chosen generator can realize a plan and retain useful
component boundaries; never count a good plan as a good generated object.
