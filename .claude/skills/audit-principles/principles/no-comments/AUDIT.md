# no-comments

**Rule:** code and tests carry no comments. What a comment would say goes into a name, a test or a commit message. Test titles, skip reasons, test names and test file names carry no history ids (the `code-writing` convention, "No comments" and "Test names").

**Terms.** A *comment* is a line, block, doc or `MARK:` comment in TS/JS, Swift or CSS. `//` inside a string, template, regex literal or Swift raw or multi-line string is not one, and neither is a shebang. Two comments are always allowed: a generated-code marker (`@generated`, `Code generated … DO NOT EDIT`) and, in TS/JS, `eslint-disable-next-line <one rule> -- <reason>`. The config's `allow` regexes, matched against a comment's text, add any lint directive the repo agrees to keep. A *history id* is a ticket key (`<key>-<n>` for each of the config's `ticket_keys`), a behavior number (`behavior 4`, `B2-1`), a QA case or ambiguity id (`QA-B3`, `AMB-1`), or an artifact name (`contract.md`, `test-plan`). *Test files* are the files the config's `tests` globs match.

**Scripts** (this module's folder, stdlib Python 3.9+, run with `python3 -I`):

- `audit.py propose` drafts a config and prints, per root and language, the lines, comments and rate per 1k; the comments' most common leading words, where lint directives show up; and the most commented files.
- `audit.py sample` prints every Nth comment, tagged `code` (reads as commented-out code) and `history`, plus every history-id violation.
- `check.py --report` prints every violation, per-root and per-language counts, and how many comments each exception allowed.
- `test_check.py` tests both scripts: `python3 -I -m unittest discover -s <module> -p 'test_*.py'`. Run it after changing either.

`check.py` rules: `comment` (a comment no exception allows) and `history-id` (a history id in a test file's title, skip or expected-fail reason, declared function or type name, or file name). A comment's baseline key is its file, kind and a hash of its text, so it survives moved lines and other comments coming and going; rewording a baselined comment makes it new. A history id's key is its file, place and the id.

## Measure

1. **Draft or load the config.** First audit: `audit.py propose --root . --out <scratch>/config.json`. Re-measure: use `controls/no-comments/config.json`.
2. **Count.** `check.py --report --config <config>`. Note the rate per language: one clean language beside a dirty one is the usual gap.
3. **Judgment sample.** Run `audit.py sample --config <config>`. Open every sampled comment outside CSS and the first 10 in CSS, plus every history-id hit, and decide:
   - **Lint directive?** A suppression with a reason (`@ts-expect-error — <reason>`, `swiftlint:disable:next <rule> — <reason>`) is an `allow` candidate. One without a reason is a violation.
   - **What would it become?** A why becomes a test or a name, change history goes to the commit message, a section banner goes away. Count the comments that explain a guard, such as a `catch {}`: deleting them leaves the guard unexplained, so their slice adds a log or a test.
   - **Generated or fixture?** A file a generator writes, or a test fixture holding source text, is an exclude candidate.
4. **Cross-check the lexer.** `grep -rnE '^\s*(//|/\*)'` over each root. Every grep hit the report lacks must be text inside a literal.
5. **Recency.** `git log --since=<30 days ago> -p -- <file> | grep -E '^\+.*(//|/\*)'` on the most commented files: are agents still adding comments there?
6. **Existing enforcement.** Look for an ESLint comment rule (`no-warning-comments`, a custom `no-comments` plugin), SwiftLint custom rules on `//`, a stylelint rule on CSS comments, and a guard against disabling them. Trace the CI step that runs each. A rule CI never runs is not enforcement. Note which languages, test names and skip reasons each rule leaves out.

## Agree (first audit)

Present these in order. After every change, rerun `check.py --report` on the edited config and show the new counts.

1. **Roots and excludes.** Code and tests both count, and so do tooling scripts unless the user excludes them. List every exclude with its reason: generated files, vendored code, fixtures holding source text.
2. **Allowed directives.** Each `allow` regex, with its count and an example. Recommend anchored patterns that require a reason (`^@ts-expect-error\s+[—-]+\s+\S`), so a bare suppression still fails.
3. **Tests and ticket keys.** The `tests` globs, and the `ticket_keys` propose read from git history. Drop a key that is a real word or unit in this repo.
4. **Strictness.** One row per rule with its count. Recommend `strict` at zero and `baseline` above it, so only new violations fail. Use `off` only when the user doesn't want the rule yet.
5. **Existing enforcement**, from Measure step 6: keep it, replace it, or run both. Never install a second comment check silently.

**New codebase** (a few dozen source files, or no comments yet): agree the roots, `tests` and `ticket_keys`, leave `allow` empty, and make every rule `strict`.

Write the approved config to `controls/no-comments/config.json`.

## Rubric

Rates are comments per 1k lines, per language, across all roots.

- **5**: ≤ 0.1 per 1k in every language, no history ids in test names, and CI fails a new comment.
- **4**: one language or one file is a blind spot, with the main language clean.
- **3**: comments are common in core modules.
- **2**: comments are common across several modules.
- **1**: comments everywhere.

Lower a score by one when the sample shows history ids or commented-out code are the norm in the comments that remain.

## Refactor targets

Size each target in comments or ids, largest first:

- **Strip one file or module**: each why becomes a test or a name, each history line goes, each banner goes.
- **Rename the tests**: titles, skip reasons and file names named after the behavior, without the id.
- **Close an enforcement gap** in an existing lint rule that misses a language, test file names or skip reasons.
