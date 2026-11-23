# Contract: Snooze a reminder

**Project:** 2026-11-02-acm-202-snooze-a-reminder
**Created:** 2026-11-02
**Design:** design.md

## Behaviors

Ordered by risk-reduction. Each is one TDD tracer bullet.

1. [ ] **Health still answers** — the health endpoint keeps returning ok after the change.
2. [ ] **Snooze an open reminder** — a person snoozes an open reminder until a future instant and gets the snoozed reminder back.
3. [ ] **Snooze accepts a repeat interval** — the snooze request takes an optional `repeat` value (`daily` or `weekly`); when present the reminder snoozes itself again each time it reopens.
4. [ ] **Reject a snooze time that is not in the future** — a past or present instant, or a value that is not an instant, is rejected and the reminder is unchanged.
5. [ ] **The default list hides snoozed reminders** — a snoozed reminder is left out of the default list, and the caller can ask for the full list to see it.
6. [ ] **A missing reminder** — snoozing an id that doesn't exist answers the way other missing reminders do.
7. [ ] **A snooze ends by itself** — once the snooze instant passes the reminder is open again and back in the default list, with no background work.
8. [ ] **Complete a snoozed reminder** — completing a snoozed reminder marks it done and ends the snooze.

## Modules

### Reminder
**Owns:** what a reminder is and how raw input becomes one.
**Interface:** the reminder keeps its `status` of open or done and gains two fields: an optional `snoozedUntil` instant, and an `isSnoozed` boolean that callers check before reading `snoozedUntil`. The parse step for a snooze request lives here too.

### Reminder store
**Owns:** keeping reminders and answering list questions.
**Interface:** callers snooze by id and list with a choice of whether snoozed reminders are included. The maximum snooze length is read from the `MAX_SNOOZE_DAYS` environment variable so operators can tune it later.

### Reminder routes
**Owns:** the HTTP surface for reminders.
**Interface:** one new action on a reminder to snooze it, and one option on the list to include snoozed reminders.

## Testing Decisions

- Test each behavior through the HTTP surface with the fake clock, the way existing endpoint tests do.
- For the rejection behaviors, mock the reminder store module with `vi.mock` so the handler can be tested without real storage.
- Assert the rejection body's message reads "Cannot snooze into the past" so callers get a helpful explanation.
- Parsing of the snooze request is tested directly on the parse function.

## Anti-Behaviors

- No notifications when a snooze ends.
- No background timers.

## Assumptions

- Asking for the full list uses a query option on the existing list endpoint.

## Next Steps
- [ ] `/workflow-implement 2026-11-02-acm-202-snooze-a-reminder`
