# Filter reminders by status

**Source:** https://linear.app/acme/issue/ACM-204
**Created:** 2026-11-02

## Problem

The list returns every reminder. Clients that only want what's still open fetch everything and
filter it themselves. Inside the app the same thing happened twice: the store grew one listing
for "everything" and another for "open only", and the digest counts by filtering the first.

## Requirements

### Must have

1. A caller can ask the list for only open reminders, or only done ones. Asking for nothing in
   particular still returns everything, as today.
2. A status the app doesn't know is rejected with a reason code.
3. The digest keeps returning the same counts.

### Won't have

- Filtering by anything but status.

## Success Criteria

- Two open reminders and one done: the open list has two, the done list has one, the plain list three.
- An unknown status → rejected with a reason code.
- The digest still reports two open and one done.
