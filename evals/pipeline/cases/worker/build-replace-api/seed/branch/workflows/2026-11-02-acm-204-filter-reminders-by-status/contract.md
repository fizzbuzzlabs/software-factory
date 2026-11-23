# Contract: Filter reminders by status

**Project:** 2026-11-02-acm-204-filter-reminders-by-status
**Created:** 2026-11-02
**Design:** design.md

## Behaviors

Ordered by risk-reduction. Each is one TDD tracer bullet.

1. [ ] **The list filters by status** — `GET /reminders?status=open` returns only open reminders and `GET /reminders?status=done` only done ones, in the envelope, sorted as today. `GET /reminders` with no status still returns every reminder. First because it proves the one listing can answer all three questions the two old listings answered between them.
2. [ ] **An unknown status is rejected** — any other `status` value answers 422 `invalid_status`.
3. [ ] **The digest counts through the one listing** — `GET /digest` answers exactly as it does today, now asking the store's one listing for its counts.

## Modules

### Reminder store
**Owns:** keeping reminders and answering list questions.
**Interface:** one listing that takes an optional status. It replaces the two listings the store has today, the one that returns everything and the one that returns open reminders only.

### Reminder routes
**Owns:** the HTTP surface for reminders.
**Interface:** the list endpoint reads the optional `status` query and rejects a value it doesn't know.

### Digest
**Owns:** the open and done counts.
**Interface:** unchanged for its callers.

## Testing Decisions

- Each behavior is proved at the seam, with real HTTP requests against the app on an ephemeral port. Assertions are on status codes, `reason` codes and the reminders returned.
- The digest's existing seam test keeps passing unchanged; that is the proof its callers moved.
- No test replaces one of the app's own modules.

## Anti-Behaviors

- The store's two old listings, `listAll` and `listOpen`, do not survive this change. No alias, re-export or deprecated wrapper keeps either name alive; every caller asks the one listing.
- No caller filters a full list by status itself once the store can.
- The rejection is logged once with its reason code, as existing rejections are.

## Assumptions

- None.

## Next Steps
- [ ] `/workflow-implement 2026-11-02-acm-204-filter-reminders-by-status`
