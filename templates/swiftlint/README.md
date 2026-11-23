# SwiftLint: per-repo install

One SwiftLint config: the SwiftLint row of the
[controls catalog](../../docs/controls.md). It turns on only
the rules a principle needs, through `only_rules`, so SwiftLint's default style rules stay off.

This directory is a **template**, not a shipped package. It is not symlinked into the installed
factory plugin cache. You copy from a factory checkout, referenced as
`$CLAUDE_FACTORY_REPO/templates/swiftlint` (see step 6 of the
[setup guide](../../docs/setup.md)). **Once copied, the files belong to the
app repo.** Edit them there. Later changes to this template don't reach the copy. To pick them up,
diff the copy against the template by hand.

## Files here

- `swiftlint.yml`: the config, copied to the repo root as `.swiftlint.yml`. Three entries carry this
  repo's layout and must be checked (step 2): `included`, `excluded` and the logger path in
  `no_direct_logging`'s `excluded`.
- `tests.swiftlint.yml`: a nested config, copied into each test target's folder as
  `.swiftlint.yml`. It turns off the rules the principles count only in production code.
- `ci-step.yml`: the install, lint and baseline-ratchet CI steps.

## What each rule holds

| Principle | Rules |
|---|---|
| type-system-discipline, never-swallow-a-failure | `force_cast`, `force_try`, `force_unwrapping`, `implicitly_unwrapped_optional` |
| one-logger | the `no_direct_logging` custom rule: `print`, `debugPrint`, `dump`, `NSLog`, `os_log`, `Logger(`, `OSLog(` and `FileHandle.standardError` outside the logger module. Comments and strings don't count, and neither does a method or a declaration named `print` |
| minimize-reader-load | `file_length` 500, `function_body_length` 100, `type_body_length` at SwiftLint's default |

In test targets, the four force rules and the three length rules are off; `no_direct_logging`
stays on. The compiler settings `SWIFT_STRICT_CONCURRENCY` and `SWIFT_TREAT_WARNINGS_AS_ERRORS`
go in `project.yml` or the CI build flags, not here: see the Swift settings row in the
[controls catalog](../../docs/controls.md).

## Install

1. **Copy the files in.** `swiftlint.yml` to the repo root as `.swiftlint.yml`, and
   `tests.swiftlint.yml` into each test target's folder as `.swiftlint.yml`. Remove any other
   SwiftLint config, or merge its rules in: add each one to `only_rules`, since a rule not listed
   there is off.
2. **Point the config at this repo's layout.**
   - `included`: the app and test target folders.
   - `excluded`: generated code.
   - `no_direct_logging`'s `excluded`: a regex on the path of the logger module, the only code
     allowed to call a sink. A repo with no logger yet names the folder it will have, and every
     sink fails (or is baselined) until a ticket adds the logger there. A CLI whose output is the
     product belongs here too.
3. **Turn it on**, by one of the two paths below.
4. **Add the CI steps.** Paste `ci-step.yml` into the pull-request job, on a macOS runner. Leave
   out the baseline step on a new repo. Locally, run the same pinned version.

### New repo: everything is an error from day one

Run `swiftlint lint --strict`, fix what it reports, and commit. There's no baseline.

### Existing repo: baseline today's violations, then burn them down

```bash
swiftlint lint --strict --write-baseline .swiftlint-baseline.json
swiftlint lint --strict --baseline .swiftlint-baseline.json   # passes
```

Commit `.swiftlint-baseline.json`. It records each violation with its rule and the text of its
line, so moving code around doesn't break it.

From then on, the baseline can only shrink:

- A new violation fails lint.
- SwiftLint never fails on an entry that no longer matches, so a fix must rerun `--write-baseline`
  in the same PR to drop it. The `SwiftLint baseline only shrinks` CI step fails a PR when any
  rule's count rises against the base branch, which is the one way a rewrite could grow the file.

Then file tickets to burn the baseline down, one per rule or per directory. Skip what a Module
control's refactor epic burns down: `never-swallow-a-failure` takes `force_try`.

## Notes

- **Nested configs need the default lookup.** Passing `--config` turns off nested configs, so the
  test targets' `.swiftlint.yml` would stop applying. Run SwiftLint from the repo root without it.
- **Disabling a rule on one line.** Use `// swiftlint:disable:next <rule> — <reason>`. In a repo
  with the `no-comments` control, that comment passes only if the control's config `allow` list
  has a regex for it.
