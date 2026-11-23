# Design: Reject reminders due in the past

**Project:** 2026-11-02-acm-206-reject-reminders-due-in-the-past

## Key decisions

1. **The rule lives with the other new-reminder rules.** The code that turns a raw request body
   into a new reminder already owns the title and due-instant rules; "not in the past" is one more,
   judged against the injected clock.
   - Alternative considered: check in the route handler after parsing. Rejected: a new-reminder
     rule outside the place that owns new-reminder rules.
2. **That code is renamed first.** It is named for request bodies in general (`body`, `checkBody`),
   which was already vague and becomes wrong once it reads the clock. It is renamed for what it
   produces before the rule is added, so the rename and the new rule can be reviewed apart.
3. **The rejection follows the existing pattern:** 422 with a reason code, logged once.
