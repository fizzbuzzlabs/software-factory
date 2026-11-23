# Research

**Project:** __FOLDER__

## How reminders work today

- A reminder has an id, a title, a due instant and a status.
- Raw request bodies are parsed into domain values in one place, the reminder module; nothing
  downstream re-validates.
- The store keeps reminders in memory. The list comes back sorted by due instant, then id.
- Time comes from an injected clock and ids from an injected id source, so tests control both.
- Every handler answers with the envelope: `data` on success, `error.reason` on rejection. Each
  rejection is logged once with its reason code through the one logger.

## Tests today

- Parsing rules are tested directly on the parse function.
- Endpoint behavior is tested at the seam: the app is started on an ephemeral port with a fake
  clock and id source, and called with real HTTP requests. Assertions are on status and reason
  codes and on JSON structure.
