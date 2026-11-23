# Snooze a reminder

**Source:** https://linear.app/acme/issue/ACM-201
**Created:** 2026-11-02

## Problem

People create a reminder, see it come due at a bad moment, and have only two choices: leave it
cluttering the list or mark it done when it isn't. They want to put it off until a time they pick.

## Requirements

### Must have

1. A person can snooze an open reminder until an instant they choose. While it is snoozed it is
   out of the way: the default reminder list leaves it out.
2. When the snooze time passes, the reminder is open again by itself and shows up in the default
   list. Nothing has to run in the background for this to be true, and no restart is needed.
3. A person can ask for the full list, snoozed reminders included, so they can find one they put off.
4. A snooze time that is not in the future is rejected. So is one that isn't a valid instant.
5. A reminder that is already done can't be snoozed. The person is told why.
6. Snoozing a reminder that doesn't exist answers the same way every other missing reminder does.
7. Completing a snoozed reminder works and ends the snooze.

### Won't have

- Recurring snoozes, or "snooze for 10 minutes" shortcuts. The caller always sends the instant.
- Notifications when a snooze ends.
- Any change to how reminders are created or listed for callers who never snooze.

## Notes for whoever designs this

- Today a reminder is either open or done, and that is stored as one field. Snoozing adds a third
  situation that carries its own data (the time it ends).
- Every response uses the app's envelope and every rejection carries a reason code, like the
  existing endpoints.

## Success Criteria

- Snooze an open reminder until tomorrow → the default list no longer shows it; the full list does.
- Snooze a reminder until two seconds from now, wait three → the default list shows it again.
- Snooze with a time in the past → rejected with a reason code, reminder unchanged.
- Snooze a done reminder → rejected with a reason code, reminder unchanged.
- Complete a snoozed reminder → it is done, and no longer snoozed.
