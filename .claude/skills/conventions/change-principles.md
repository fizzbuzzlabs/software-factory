# Convention: Change Principles

Each `Change` principle from the factory's engineering principles, as what each pipeline stage does about it. **Contract** lines bind whoever writes or amends `contract.md`; **Implement** lines bind `workflow-implement`. Where a gate already holds a principle, its line names the gate.

## laziness-protocol

Make the smallest change that solves the problem.

- **Contract:** every option, field, parameter or extension point names the production caller that sets it, in this contract. Cut what has none, and any gold-plating the spec doesn't ask for.
- **Implement:** add no parameter, option or union member that no production caller sets, and no generic or strategy with one instantiation. A test seam over I/O (clock, fetch, ids, an external client) is fine.

## migrate-callers-then-delete-legacy-apis

When a new internal API replaces an old one, move every caller and delete the old one in the same change.

- **Contract:** `## Anti-Behaviors` names each API the change replaces as not surviving it.
- **Implement:** keep no re-export, renamed alias or deprecated declaration alive for callers; point them at the replacement.

## outcome-oriented-execution

Converge on the target. Don't keep an intermediate state alive with compatibility code.

- **Contract:** `## Anti-Behaviors` also names each route, CLI, env var, flag or storage shape the change replaces. A replacement that spans repos is lanes in this contract (`workflow-contract` **Lanes**), not a later ticket. Anything that must stay live goes under `## Assumptions` with its removal ticket filed through `create-ticket` and linked. A deliberate, permanent split, such as one path per platform, isn't transitional.
- **Implement:** ship no bridge the contract doesn't list: no "no longer used" warning, no rollout flag left off by default, no old storage idiom carried onto a new store.

## prove-it-works

Check the change against the real thing, not a proxy.

- **Contract:** held by `workflow-contract`'s Seam rule.
- **Implement:** held by `workflow-implement`'s done check on each behavior and its verify gate.

## redesign-from-first-principles

When a requirement changes an existing type, redesign the type as if the requirement had been there from day one.

- **Contract:** for each existing type the change alters, `## Modules` says whether it is **rebuilt** (restructured, old shape deleted) or **extended** (a new variant with its own payload, or a new required field). Never a bolt-on:
  - a sub-flag on an existing enum member (`status: "needs-input"` plus `forReview: true`);
  - an optional field or boolean that only means something under one value of another field;
  - old and new shapes kept side by side.

  Every reader of a rebuilt type moves to the new shape in this contract.
- **Implement:** when the code shows the contract's shape needs a bolt-on to work, that is a contract mismatch to raise as `workflow-implement` says, not a flag to add.

## sequence-verifiable-units

Work in small units that each end verified, so a reviewer takes in each one at a sitting.

- **Contract:** order behaviors by risk reduction: the first is the smallest end-to-end proof of the riskiest assumption, never the happy path first.
- **Implement:** each `behavior N:` commit leaves typecheck and its scoped tests green. A later commit never repairs a gate an earlier one broke, and nothing is committed as work in progress.

## subtract-before-you-add

Remove dead weight first, then build on the simpler base.

- **Implement:** before adding a helper, validator or test, search for one that already does the job and reuse or extend it. Delete what the change orphans, such as a helper whose last caller you removed. The debt-ratchet gate holds duplication.

## tidy-first

Put structural and behavioral changes in different commits.

- **Implement:** a rename, move or extract that a behavior needs lands first as its own `<TICKET> tidy: <what>` commit, before that behavior's RED. A `behavior N:` commit carries no unrelated rename or move; REFACTOR's own commit holds the cleanup.
