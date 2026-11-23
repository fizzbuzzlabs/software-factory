import type { Reminder } from "./reminder.js";

export type ReminderStore = {
  add(reminder: Reminder): void;
  get(id: string): Reminder | undefined;
  list(): Reminder[];
  markDone(id: string): Reminder | undefined;
  rename(id: string, title: string): Reminder | undefined;
};

function byDueAtThenId(a: Reminder, b: Reminder): number {
  const difference = Date.parse(a.dueAt) - Date.parse(b.dueAt);
  if (difference !== 0) return difference;
  return a.id < b.id ? -1 : 1;
}

export function createReminderStore(): ReminderStore {
  const reminders = new Map<string, Reminder>();
  return {
    add(reminder) {
      reminders.set(reminder.id, reminder);
    },
    get: (id) => reminders.get(id),
    list: () => [...reminders.values()].sort(byDueAtThenId),
    markDone(id) {
      const reminder = reminders.get(id);
      if (reminder === undefined) return undefined;
      const done: Reminder = { ...reminder, status: "done" };
      reminders.set(id, done);
      return done;
    },
    rename(id, title) {
      const reminder = reminders.get(id);
      if (reminder === undefined) return undefined;
      const renamed: Reminder = { ...reminder, title };
      reminders.set(id, renamed);
      return renamed;
    },
  };
}
