# never-swallow-a-failure

**Rule:** every failure is handled, propagated, or logged with context. Never an empty catch, a default returned with no log, a floating promise rejection, a `try?` that drops an error that matters, or a force `try!`.

**Terms.** A *handler* is a `catch` block or a `.catch(...)` callback. A handler *swallows* when the failure leaves no trace: no rethrow, no typed failure, no error state, no log. A *floating* promise is one nobody awaits or catches; in the browser its rejection vanishes, in Node it can kill the process. A *probe* is a call whose failure is the answer: `new URL()` validity, `JSON.parse` of a request body that becomes a 400. *Production code* is everything under the roots that the config doesn't exclude; tests, scripts and generated code are excluded.

**Scripts** (this module's folder, stdlib Python 3.9+, run with `python3 -I`):

- `audit.py propose` drafts a config and prints per root the lines, each rule's count and violations per 10k lines, the files with the most violations, and lint configs that mention a related rule.
- `audit.py sample` is the judgment sample. It classifies every non-empty handler as PROPAGATE, LOG or OTHER and lists every Swift `try?` used inside an expression. `--log` replaces the logger regex when the repo's logger has an unusual name.
- `audit.py lint` counts per root what the lint rules below find, from ESLint and SwiftLint JSON output.
- `check.py --report` prints every violation and per-root counts under a config.
- `test_check.py` tests both scripts: `python3 -I -m unittest discover -s <module> -p 'test_*.py'`. Run it after changing either.

`check.py` rules:

- `empty-catch`: a `catch` block with no statements once comments are stripped. In TS, only one that holds comments; `no-empty` finds the rest.
- `discarded-try` (Swift): a statement that is `try? ...` or `_ = try? ...`, dropping the error and the result. `try? await Task.sleep` doesn't count: only cancellation reaches it.
- `throwing-task` (Swift): a `Task { ... }` or `Task.detached { ... }` statement, not assigned, whose body has a `try` and no `catch`. Its error is dropped.

A violation's baseline key is its file, rule, kind (`catch`, `try? <callee>`, `Task`) and occurrence number, so moving lines doesn't change it.

**Lint rules** hold the rest of the principle; `check.py` leaves it to them. TS: the ESLint template's `no-floating-promises` (`ignoreVoid: false`), `no-misused-promises`, `no-empty` (`allowEmptyCatch: false`) and its `no-restricted-syntax` selector on a `.catch()` callback that does nothing. Swift: SwiftLint `force_try`.

Not checked: a handler that returns a default with no log; `try?` inside an expression; force unwraps and `as!` (`swiftlint-no-force-unwrap`, `swiftlint-no-force-cast`); whether a log line carries context. The judgment sample covers the first two.

## Measure

1. **Lint.** Every TS root needs the ESLint template (`$CLAUDE_FACTORY_REPO/templates/eslint`) with the rules above, and every Swift root SwiftLint with `force_try` on, each run by a CI step. `audit.py propose` prints the lint configs that mention them. A rule CI never runs is not enforcement, and SwiftLint's `only_rules` switches off every rule it doesn't name. If one is missing, stop and say so: the audit can't count what it holds. It's installed first, in its own PR. Then write `npx eslint . --format json -o <scratch>/eslint.json` and `swiftlint lint --quiet --reporter json > <scratch>/swiftlint.json`.
2. **Draft or load the config.** First audit: `audit.py propose --root . --out <scratch>/config.json`. Re-audit: use `controls/never-swallow-a-failure/config.json`.
3. **Count.** `check.py --report --config <config>`, then `audit.py lint --config <config> --lint <scratch>/eslint.json --lint <scratch>/swiftlint.json`.
4. **Floating promises.** For each `floating-promise` and `misused-promise` finding, open the callee: does it catch internally, or can it reject? Transports that throw on non-2xx can. Note whether the repo has an `unhandledrejection` listener or a crash handler; neither makes a rejection handled.
5. **Judgment sample.** Run `audit.py sample --config <config>`. Open every OTHER handler and every expression `try?`; that's where a default with no log hides. Open a dozen PROPAGATE and LOG handlers to check the regex. Classify each as handled, propagated, logged, probe, minor (best-effort cleanup such as `reader.cancel()` while the primary error propagates, or a display fallback) or **swallowed**: the failure means lost data or a misreported state, and nothing records it.

These never count: probes; a failure converted to a typed result (`{ ok: false, reason }`, `.failure(.decodeFailed)`, an HTTP 4xx or 5xx); a fallback a log line or a pinning test documents. Guards against impossible states belong to fix-root-causes. Whether logs reach one sink belongs to one-logger.

## Agree (first audit)

Present these in order. After every change, rerun `check.py --report` on the edited config and show the new counts.

1. **Excludes.** Tests, scripts, generated code. List every exclude beyond the drafted test patterns, with the reason.
2. **Strictness.** One row per rule with its count. Recommend `strict` at zero and `baseline` above it, so only new violations fail. Use `off` only when the user doesn't want the rule yet.

**New codebase** (a few dozen source files): every rule `strict`.

Write the approved config to `controls/never-swallow-a-failure/config.json`.

## Rubric

Count swallowed sites: check and lint findings whose failure can really occur (a floating promise whose callee can reject, any empty handler that isn't cleanup), plus the handlers and `try?` the sample judged swallowed. Normalize per 10k production lines.

- **5**: ≤ 1 per 10k, all peripheral, and CI fails a new one.
- **4**: a handful in core paths, no recurring shape.
- **3**: core-path swallows in more than one module.
- **2**: one swallow shape (fire-and-forget UI actions, empty stream catches) recurs across several modules.
- **1**: swallowing is the default.

## Refactor targets

Size each target in sites, largest first:

- **Route fire-and-forget actions through one helper**, such as `runAction(name, fn)`, that catches, logs with context and sets an error state. One target per root; it usually clears most `floating-promise` findings.
- **Fix one stream or subscriber** whose catch is empty or logs only sometimes: log, then retry with backoff or surface the error.
- **Log or narrow the defaults**: each swallowed handler from the sample gets a log line, a typed failure, or a narrower catch (`NotConnectedError` apart from a DB outage).
- **Swift**: `do`/`catch` with a log in place of each `discarded-try` and `try!`, and a `catch` inside each `throwing-task`.
