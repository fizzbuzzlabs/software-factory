# List snoozed reminders by wake time

**Source:** https://linear.app/acme/issue/ACM-207
**Created:** 2026-11-03

## Problem

Once people can snooze reminders, they lose track of what they put off and when it comes back.
They want one place that shows only their snoozed reminders, the one that wakes up soonest first.

## Requirements

### Must have

1. A person can ask for just their snoozed reminders, and gets each one with the instant it wakes up.
2. The list is ordered by wake-up instant, soonest first.
3. A reminder whose snooze has already ended is not in this list.
4. With nothing snoozed, the answer is an empty list, not an error.

### Won't have

- Changing how snoozing itself works.
- Any change to the existing reminder list.

## Success Criteria

- Snooze two reminders until tomorrow and next week → the snoozed list shows tomorrow's first.
- A snooze that ended a minute ago → that reminder is not in the snoozed list.
- Nothing snoozed → an empty list.
