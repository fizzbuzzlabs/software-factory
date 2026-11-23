import type { Clock } from "../kernel/clock.js";
import { asOf, inSituation, type Reminder, type Situation } from "./reminder.js";

export type ReminderStore = {
  add(reminder: Reminder): void;
  get(id: string): Reminder | undefined;
  list(which: "unsnoozed" | "all"): Reminder[];
  markDone(id: string): Reminder | undefined;
  snooze(id: string, until: string): Reminder | undefined;
};

function byDueAtThenId(a: Reminder, b: Reminder): number {
  const difference = Date.parse(a.dueAt) - Date.parse(b.dueAt);
  if (difference !== 0) return difference;
  return a.id < b.id ? -1 : 1;
}

export function createReminderStore(clock: Clock): ReminderStore {
  const reminders = new Map<string, Reminder>();
  const get = (id: string): Reminder | undefined => {
    const reminder = reminders.get(id);
    return reminder === undefined ? undefined : asOf(reminder, clock.now());
  };
  const move = (id: string, situation: Situation): Reminder | undefined => {
    const reminder = get(id);
    if (reminder === undefined) return undefined;
    const moved = inSituation(reminder, situation);
    reminders.set(id, moved);
    return moved;
  };
  return {
    add(reminder) {
      reminders.set(reminder.id, reminder);
    },
    get,
    list(which) {
      const now = clock.now();
      return [...reminders.values()]
        .map((reminder) => asOf(reminder, now))
        .filter((reminder) => which === "all" || reminder.status !== "snoozed")
        .sort(byDueAtThenId);
    },
    markDone: (id) => move(id, { status: "done" }),
    snooze: (id, until) => move(id, { status: "snoozed", snoozedUntil: until }),
  };
}
