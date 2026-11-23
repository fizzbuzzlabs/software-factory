# Contract: Overdue reminders

**Project:** 2026-11-02-acm-207-overdue-reminders
**Created:** 2026-11-02
**Design:** design.md

## Behaviors

Ordered by risk-reduction. Each is one TDD tracer bullet.

1. [ ] **The overdue view answers in the running app** — `GET /overdue` answers 200 with, in the envelope, the reminders that are open and whose due instant is earlier than now, oldest due first. A reminder due later is left out.
2. [ ] **A done reminder is never overdue** — completing an overdue reminder takes it out of `GET /overdue`.

## Modules

### Overdue
**Owns:** the question "what is open and past due right now".
**Interface:** a feature of its own, beside reminders and the digest, with its own route. It reads the reminder store and the clock; nothing else changes to serve it.

## Testing Decisions

- Each behavior is proved at the seam with real HTTP requests against the app on an ephemeral port, with the fake clock moved past a reminder's due instant.
- Assertions are on the status code and on which reminders come back, by id.
- No test replaces one of the app's own modules.

## Anti-Behaviors

- The existing list and digest answer exactly as before.
- Nothing is stored about a reminder being overdue.

## Assumptions

- A reminder due exactly now is not overdue yet.

## Next Steps
- [ ] `/workflow-implement 2026-11-02-acm-207-overdue-reminders`
