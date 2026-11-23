# Research: Snooze a reminder

**Project:** 2026-11-02-acm-202-snooze-a-reminder

## How reminders work today

- A reminder has an id, a title, a due instant and a status that is either open or done.
- Raw request bodies are parsed into the reminder type in one place, the reminder module; nothing
  downstream re-validates.
- The store keeps reminders in memory. The list comes back sorted by due instant, then id.
- Time comes from an injected clock, and ids from an injected id source, so tests control both.
- Every handler answers with the envelope: `data` on success, `error.reason` on rejection. Each
  rejection is logged once with its reason code through the one logger.

## Tests today

- Parsing rules are tested directly on the parse function.
- Endpoint behavior is tested at the seam: the app is started on an ephemeral port with a fake
  clock and id source, and called with real HTTP requests. Assertions are on status and reason
  codes and on JSON structure.

## What snoozing touches

- The status field, which today has two values and no per-status data.
- The list, which today returns everything.
- The complete action, which today only moves open to done.
