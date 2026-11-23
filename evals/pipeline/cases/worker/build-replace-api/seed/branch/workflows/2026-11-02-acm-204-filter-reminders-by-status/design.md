# Design: Filter reminders by status

**Project:** 2026-11-02-acm-204-filter-reminders-by-status

## Key decisions

1. **One listing, with an optional status.** The store answers one question, "list reminders,
   optionally only those with this status", and every caller asks it that way.
   - Alternative considered: add a third listing for done reminders beside the two that exist.
     Rejected: three near-copies of one loop, and the next filter makes four.
2. **The two listings the store has today are replaced, not kept.** Their callers move in the same
   change.
3. **The filter is a query on the existing list endpoint**, and an unknown value is a rejection
   with a reason code, like every other bad input.
