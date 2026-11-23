# Engineering principles

The principles the factory holds app repos to, and what enforces each one. Many come from
[pstack](https://github.com/cursor/plugins/tree/main/pstack) (poteto / Lauren Tan, MIT). Others come from
well-known software engineering authors.

Three things enforce a principle:

- **Control**: a check that `/bootstrap-controls` installs in your app repo's CI.
- **Lint**: a lint or compiler rule you copy in from a template.
- **Pipeline**: a step a factory skill, convention or agent runs before the code reaches CI.

The [controls catalog](controls.md) covers installing the first two.

| Principle | Description | Source | Enforced by | Files |
|---|---|---|---|---|
| boundary-discipline | Parse raw input into domain types where it enters; trust internal types after; keep decisions in pure functions the I/O shell calls. | pstack | Lint | [ESLint] |
| deep-modules | Simple interface, substantial behaviour behind it; callers never know a module's internals. | Ousterhout | Pipeline | [workflow-contract], [workflow-review-contract] |
| exhaust-the-design-space | For a novel decision, weigh 2–3 competing options side by side before committing. | pstack | Pipeline | [workflow-design] |
| fix-root-causes | Trace a symptom to the first place the system went wrong and fix it there; a guard is a fix only when its state is legitimate. | pstack | Lint, Pipeline | [ESLint], [Swift settings](controls.md), [report-bug] |
| group-by-feature | A feature's code lives in its own folder, and features use each other only through edges the feature map declares. | Martin | Control | [group-by-feature] |
| guard-the-context-window | Route bulk reads and large outputs to subagents; keep summaries, not raw payloads, in the main thread. | pstack | Pipeline | [workflow-research], [codebase-* agents] |
| laziness-protocol | The smallest change that solves the problem; no abstractions, options or threaded signals the problem doesn't need. | pstack | Pipeline | [change-principles], [workflow-questions] |
| migrate-callers-then-delete-legacy-apis | When a new internal API replaces an old one, migrate every caller and delete the old one in the same wave. | pstack | Control, Pipeline | [migrate-callers-then-delete-legacy-apis], [change-principles] |
| minimize-reader-load | Count the layers between a question and its answer and the hidden state a reader holds; collapse wrappers, shrink mutable scope. | pstack | Lint | [ESLint], [SwiftLint] |
| model-the-domain | Encode the domain in one structure instead of conditionals scattered over the codebase. | pstack | Lint | [ESLint] |
| never-block-on-the-human | Proceed on reversible work and present the result; confirm only irreversible actions. | pstack | Pipeline | [execution-mode] |
| never-swallow-a-failure | Every failure is handled, propagated or logged with context. | Hunt & Thomas | Control, Lint | [never-swallow-a-failure], [ESLint], [SwiftLint] |
| no-comments | Code and tests carry no comments; what a comment would say goes into a name, a test or a commit message. | pstack | Control, Pipeline | [no-comments], [code-writing] |
| one-logger | Logging is structured, levelled, and goes through one module. | — | Lint | [ESLint], [SwiftLint] |
| outcome-oriented-execution | Converge on the target architecture; don't keep intermediate states alive with throwaway compatibility code. | pstack | Pipeline | [change-principles] |
| prove-it-works | Check a change against the real thing: run the feature, read the actual value. | pstack | Pipeline | [workflow-implement] (verify gate), [workflow-contract], [change-principles] |
| redesign-from-first-principles | A new requirement redesigns the type as if it had been there from day one, instead of bolting on. | pstack | Pipeline | [change-principles] |
| separate-before-serializing-shared-state | When concurrent actors might write the same row or object, eliminate the sharing first; serialize only when one writer is a real invariant. | pstack | Lint | [Swift settings](controls.md) |
| sequence-verifiable-units | Small units that each end in a verified state; each delivered change is one intent a reviewer takes in one sitting. | pstack | Pipeline | [change-principles], [workflow-implement] |
| subtract-before-you-add | Remove dead weight first, then build on the simpler base. | pstack | Lint, Pipeline | [ESLint], [debt ratchet], [change-principles], [workflow-implement] |
| test-behavior-not-implementation | A test asserts what users observe and reaches the code through a real caller's path; mock only what you don't own. | pstack | Lint, Pipeline | [ESLint], [code-writing], [workflow-implement], [workflow-review-contract] |
| tidy-first | Structural and behavioural changes go in different commits. | Beck | Pipeline | [change-principles], [workflow-implement] |
| type-system-discipline | Make illegal states unrepresentable, brand primitives, exhaust variants, derive types from authoritative schemas. | pstack | Lint | [ESLint], [SwiftLint] |

[ESLint]: ../templates/eslint/README.md#what-each-rule-holds
[workflow-contract]: ../.claude/skills/workflow-contract/SKILL.md
[workflow-review-contract]: ../.claude/skills/workflow-review-contract/SKILL.md
[workflow-design]: ../.claude/skills/workflow-design/SKILL.md
[report-bug]: ../.claude/skills/report-bug/SKILL.md
[group-by-feature]: ../.claude/skills/bootstrap-controls/controls/group-by-feature/CONTROL.md
[workflow-research]: ../.claude/skills/workflow-research/SKILL.md
[codebase-* agents]: ../.claude/agents/
[change-principles]: ../.claude/skills/conventions/change-principles.md
[workflow-questions]: ../.claude/skills/workflow-questions/SKILL.md
[migrate-callers-then-delete-legacy-apis]: ../.claude/skills/bootstrap-controls/controls/migrate-callers-then-delete-legacy-apis/CONTROL.md
[SwiftLint]: ../templates/swiftlint/README.md#what-each-rule-holds
[execution-mode]: ../.claude/skills/conventions/execution-mode.md
[never-swallow-a-failure]: ../.claude/skills/bootstrap-controls/controls/never-swallow-a-failure/CONTROL.md
[no-comments]: ../.claude/skills/bootstrap-controls/controls/no-comments/CONTROL.md
[code-writing]: ../.claude/skills/conventions/code-writing.md
[workflow-implement]: ../.claude/skills/workflow-implement/SKILL.md
[debt ratchet]: ../templates/debt-ratchet/README.md
