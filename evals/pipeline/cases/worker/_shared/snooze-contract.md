# Contract: Snooze a reminder

**Project:** __FOLDER__
**Created:** 2026-11-02
**Design:** design.md

## Behaviors

Ordered by risk-reduction. Each is one TDD tracer bullet.

1. __BOX__ **A snooze takes effect and ends by itself** — `POST /reminders/:id/snooze` with a JSON body `{ "until": <ISO-8601 instant> }` on an open reminder answers 200 with the reminder in the envelope, its `status` now `snoozed` and `snoozedUntil` set to that instant. Read before that instant, the reminder is snoozed. Read at or after it, the reminder is open again with no `snoozedUntil`, though nothing ran in between. First because the whole design rests on deciding "snoozed" at read time from the clock; if that doesn't hold, nothing after it matters.
2. __BOX__ **The default list leaves snoozed reminders out** — `GET /reminders` returns only reminders that are not snoozed right now. `GET /reminders?include=snoozed` returns every reminder. Both stay sorted as today.
3. __BOX__ **A snooze time must be a future instant** — an `until` that is missing, not text, not a parseable instant, or not after now answers 422 `invalid_until`, and the reminder is unchanged.
4. __BOX__ **A done reminder can't be snoozed** — answers 409 `already_done`, and the reminder is unchanged.
5. __BOX__ **A missing reminder** — snoozing an id that doesn't exist answers 404 `not_found`, like every other missing reminder.
6. __BOX__ **Completing a snoozed reminder ends the snooze** — `POST /reminders/:id/complete` on a snoozed reminder answers 200 with `status` `done` and no `snoozedUntil`.

## Modules

### Reminder
**Owns:** what a reminder is, and how raw input becomes one or becomes a snooze request.
**Interface:** the reminder type is **rebuilt**. A reminder is in exactly one situation: open, snoozed until an instant, or done. The end instant exists only in the snoozed situation; there is no such thing as an open or done reminder that still carries one, and no flag that says whether to read it. Whether a snoozed reminder still counts as snoozed is answered against the clock by this module, so every reader gets the same answer. Every reader of the old two-value status moves to the new shape in this contract.

On the wire `status` is `open`, `snoozed` or `done`, and `snoozedUntil` is present exactly when `status` is `snoozed`.

### Reminder store
**Owns:** keeping reminders and answering list questions.
**Interface:** gains one action, snooze by id until an instant; its listing is asked either for reminders not snoozed right now or for all of them.

### Reminder routes
**Owns:** the HTTP surface for reminders.
**Interface:** the snooze action and the `include=snoozed` choice on the list, as above.

## Testing Decisions

- Each behavior is proved at the seam: the app started on an ephemeral port with the fake clock and id source, called with real HTTP requests. Time passing is the fake clock moving forward, never a real wait.
- Assertions are on status codes, `reason` codes and JSON fields, including that `snoozedUntil` is absent when a reminder isn't snoozed.
- Parsing of a snooze request is tested directly on the function that owns it.
- No test replaces one of the app's own modules.

## Anti-Behaviors

- No timer, interval or background job ends a snooze.
- No recurring snooze, no duration shortcut, no notification.
- Callers who never snooze see no change: creating, reading, listing and completing answer as before for reminders that were never snoozed.
- Each rejection is logged once with its reason code, as existing rejections are.

## Assumptions

- An instant exactly equal to now is not in the future, so it is rejected.

## Next Steps
- [ ] `/workflow-implement __FOLDER__`
