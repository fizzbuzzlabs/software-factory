# Design: Snooze a reminder

**Project:** __FOLDER__

## Key decisions

1. **Snoozed is decided at read time.** A snoozed reminder stores the instant its snooze ends.
   Whether it is snoozed right now is that instant compared with the injected clock, asked every
   time the reminder is read. Nothing runs in the background.
   - Alternative considered: a timer per reminder that flips it back. Rejected: it dies on restart.
2. **The reminder's situation is one value with three shapes** (open, snoozed until, done), so the
   end instant can't exist on a reminder that isn't snoozed.
3. **The default list hides snoozed reminders; `include=snoozed` shows all.**
4. **Rejections follow the existing pattern:** a status code and a reason code in the envelope,
   logged once.

## Boundaries

- No recurring snoozes, no duration shortcuts, no notifications.
- Callers who never snooze see no change.
