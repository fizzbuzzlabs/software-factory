# Controls catalog

Everything you can install in an app repo to enforce the factory's
[engineering principles](principles.md). That page says which control enforces which principle.

Controls live in your app repo as ordinary files and run in its CI, so CI never depends on the
plugin. Each one needs CI that runs on pull requests.

The checks cover TypeScript/JavaScript, Swift and CSS only. In a repo written in another language,
none of them applies yet; the pipeline itself works in any language.

| Install | What it checks | How |
|---|---|---|
| [group-by-feature] | Every file belongs to a feature, and imports cross only the boundaries the feature map allows. TS and Swift. | `/bootstrap-controls group-by-feature` |
| [migrate-callers-then-delete-legacy-apis] | No re-export, renamed alias or deprecated declaration keeps an old API alive. TS and Swift. | `/bootstrap-controls migrate-callers-then-delete-legacy-apis` |
| [never-swallow-a-failure] | No empty `catch`, discarded `try?` or throwing `Task {}` without a `catch`. TS and Swift. | `/bootstrap-controls never-swallow-a-failure` |
| [no-comments] | No comments in TS/JS, Swift or CSS beyond agreed directives, and no ticket ids in test names. | `/bootstrap-controls no-comments` |
| [ESLint + tsconfig] | A type-aware ESLint config and a strict tsconfig fragment. | Copy `templates/eslint` and follow its README |
| [SwiftLint] | Force unwraps and casts, direct logging, and file and function length. | Copy `templates/swiftlint` and follow its README |
| [Debt ratchet] | Duplication and circular dependencies never rise past their baseline. TS. | Copy `templates/debt-ratchet` and follow its README |
| Swift settings | `SWIFT_STRICT_CONCURRENCY: complete` with `SWIFT_VERSION` 6, and `SWIFT_TREAT_WARNINGS_AS_ERRORS: YES`, at least in CI. | Add to `project.yml` or the CI build flags |

The four `/bootstrap-controls` controls first audit the repo with you to settle what counts as a
violation, then record today's violations in a baseline so CI fails only on new ones. The
templates do the same with their own baseline file.

On a new repo, install controls before much code exists: with nothing to baseline, every rule
starts strict. Install the ESLint or SwiftLint template before `never-swallow-a-failure`, which
leaves part of its principle to their rules. The templates live in a factory checkout
([setup guide](setup.md), step 6).

[group-by-feature]: ../.claude/skills/bootstrap-controls/controls/group-by-feature/CONTROL.md
[migrate-callers-then-delete-legacy-apis]: ../.claude/skills/bootstrap-controls/controls/migrate-callers-then-delete-legacy-apis/CONTROL.md
[never-swallow-a-failure]: ../.claude/skills/bootstrap-controls/controls/never-swallow-a-failure/CONTROL.md
[no-comments]: ../.claude/skills/bootstrap-controls/controls/no-comments/CONTROL.md
[ESLint + tsconfig]: ../templates/eslint/README.md
[SwiftLint]: ../templates/swiftlint/README.md
[Debt ratchet]: ../templates/debt-ratchet/README.md
