# Adversarial Test Plan: Snooze a reminder

**Project:** __FOLDER__
**Written against:** contract.md (approved), with spec.md/design.md for intent
**Mode:** black-box — every case must hold for any implementation of the contract.

## Executor notes

Start the app on an ephemeral port with the fake clock and id source. A "pass" is the status code,
`reason` code and JSON fields of the response to one real HTTP request.

## Group B1 — A snooze takes effect and ends by itself

### B1-1 — a snooze ends exactly at its instant
- **Clause:** "Read at or after it, the reminder is open again with no `snoozedUntil`"
- **Routing:** defect
- **Setup:** an open reminder snoozed until T; the clock set to exactly T
- **Action:** `GET /reminders/:id`
- **Expected:** 200, `status` is `open`, no `snoozedUntil`
- **Pass iff:** status code 200, `data.status` equals `open`, `data.snoozedUntil` is absent

### B1-2 — snoozing a reminder that is already snoozed
- **Clause:** "on an open reminder" (the contract says nothing about a snoozed one)
- **Routing:** ambiguity
- **Setup:** a reminder snoozed until T1, the clock before T1
- **Action:** `POST /reminders/:id/snooze` with `until` T2, later than T1
- **Expected:** not pinned by the contract
- **Pass iff:** not gradeable until the contract says

## Group B3 — A snooze time must be a future instant

### B3-1 — an instant equal to now
- **Clause:** "not after now answers 422 `invalid_until`"
- **Routing:** defect
- **Setup:** an open reminder; the clock at T
- **Action:** `POST /reminders/:id/snooze` with `until` T
- **Expected:** 422 `invalid_until`, reminder still open
- **Pass iff:** status code 422, `error.reason` equals `invalid_until`, a following read has `data.status` `open`

## Untestable gaps

- None.

## Findings

- **AMB-1** — blocking (the spec says people open the full list mostly to snooze a reminder again, so the request is one a real user sends, and the readings store different end times) — the contract only says what a snooze does "on an open reminder". For a reminder that is already snoozed the defensible readings are: the new instant replaces the old one; the request is rejected because the reminder isn't open; or only a later instant is accepted. Probed by B1-2.

## Gating & codification map

| Group | Gating | Home (seam / eval tier) | Cases |
|---|---|---|---|
| B1 | gate (B1-1), non-gating (B1-2) | reminders HTTP seam tests | B1-1, B1-2 |
| B3 | gate | reminders HTTP seam tests | B3-1 |

## Next Steps
- [ ] Codify keeper cases into their seam homes (after the implementation branch exists)
