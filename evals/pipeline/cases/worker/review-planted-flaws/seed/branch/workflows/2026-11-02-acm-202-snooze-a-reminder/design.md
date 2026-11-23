# Design: Snooze a reminder

**Project:** 2026-11-02-acm-202-snooze-a-reminder

## Key decisions

1. **Snoozed is computed on read.** A reminder stores the instant its snooze ends. Whether it is
   snoozed right now is decided by comparing that instant with the clock when someone asks. Nothing
   runs in the background.
   - Alternative considered: a timer per reminder that flips it back. Rejected: it dies on restart
     and the spec rules out background work.
2. **The default list hides snoozed reminders; the caller opts in to see them.**
3. **Rejections follow the existing pattern:** a status code and a reason code in the envelope,
   logged once.

## Boundaries

- No recurring snoozes, no duration shortcuts, no notifications.
- Callers who never snooze see no change in creating, listing or completing.
