# Contract: Rename a reminder

**Project:** __FOLDER__
**Created:** 2026-11-02
**Design:** design.md

## Behaviors

Ordered by risk-reduction. Each is one TDD tracer bullet.

1. __BOX__ **A rename takes effect** — `PATCH /reminders/:id` with a JSON body `{ "title": <text> }` answers 200 with the reminder in the envelope, and every later read of that reminder, alone or in the list, returns the new title. Its id, due instant and status are unchanged. First because nothing changes a reminder in place today except completing it, so this proves the store and the surface can.
2. __BOX__ **A rename follows the title rules** — the new title is held to exactly the rules a title is held to at creation: present, text, not empty once trimmed, at most 120 characters. A rename that breaks one answers 422 with the reason code creation uses, `invalid_title`, and the reminder keeps its old title.
3. __BOX__ **A missing reminder** — renaming an id that doesn't exist answers 404 `not_found`, like every other missing reminder.
4. __BOX__ **A malformed request** — a body that isn't a JSON object answers 400 `malformed_json`, like creation, and the reminder is unchanged.

## Modules

### Reminder
**Owns:** what a reminder is and the title rules. One place decides whether a title is acceptable, for creating and for renaming alike.
**Interface:** callers hand it raw input and get back either a usable title or the reason it was rejected. The reminder type itself is not changed by this contract.

### Reminder store
**Owns:** keeping reminders.
**Interface:** gains one action: rename a reminder by id, answering with the renamed reminder or that there is none.

### Reminder routes
**Owns:** the HTTP surface for reminders.
**Interface:** one new action, the `PATCH` above.

## Testing Decisions

- Each behavior is proved at the seam: the app started on an ephemeral port with the fake clock and id source, called with a real HTTP request. Assertions are on the status code, the `reason` code and the returned JSON fields.
- The title rules are tested once, directly on the function that owns them. The rename tests check that a rename is held to them, not each rule again.
- No test replaces one of the app's own modules; fakes go in through the app's dependencies.

## Anti-Behaviors

- A rename never changes a reminder's id, due instant or status.
- There is no second copy of the title rules: renaming does not get its own length limit or its own trimming.
- Each rejection is logged once with its reason code, as existing rejections are. Nothing else is logged.

## Assumptions

- A done reminder can be renamed. The spec doesn't restrict it, and a typo in a finished reminder is still a typo.

## Next Steps
- [ ] `/workflow-implement __FOLDER__`
