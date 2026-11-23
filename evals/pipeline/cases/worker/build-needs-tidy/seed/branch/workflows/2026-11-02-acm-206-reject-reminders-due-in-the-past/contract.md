# Contract: Reject reminders due in the past

**Project:** 2026-11-02-acm-206-reject-reminders-due-in-the-past
**Created:** 2026-11-02
**Design:** design.md

## Behaviors

Ordered by risk-reduction. Each is one TDD tracer bullet.

1. [ ] **A reminder due in the past is rejected** — `POST /reminders` with a `dueAt` earlier than now answers 422 `due_in_past`, and nothing is stored. A `dueAt` equal to now or later is accepted as today.

## Modules

### New-reminder parsing
**Owns:** turning a raw request body into a new reminder: the title rules, the due-instant rules, and now the not-in-the-past rule, judged against the injected clock.
**Interface:** callers hand it the raw body and the clock and get back a new reminder or the reason it was rejected.
**Renamed:** today this module and its entry point are named for request bodies in general, `body` and `checkBody`. They are renamed for what they produce: the entry point becomes `parseNewReminder` and moves into the reminder module, beside the type it produces. The rename changes no behavior and lands before the new rule.

## Testing Decisions

- The behavior is proved at the seam: a real `POST` against the app on an ephemeral port with the fake clock set to a known instant. Assertions are on the status code, the `reason` code and that the list is unchanged.
- The rule's boundary (earlier than now, equal to now, later) is tested directly on the parse function with the fake clock.
- No test replaces one of the app's own modules.

## Anti-Behaviors

- Existing reminders are never re-checked or removed because their due time has passed.
- The names `body` and `checkBody` do not survive the rename: no alias or re-export keeps them alive.
- The rejection is logged once with its reason code, as existing rejections are.

## Assumptions

- None.

## Next Steps
- [ ] `/workflow-implement 2026-11-02-acm-206-reject-reminders-due-in-the-past`
