export type Situation =
  | { status: "open" }
  | { status: "snoozed"; snoozedUntil: string }
  | { status: "done" };

export type Reminder = { id: string; title: string; dueAt: string } & Situation;

type NewReminder = Pick<Reminder, "title" | "dueAt">;

export type ParsedNewReminder =
  | { outcome: "ok"; value: NewReminder }
  | { outcome: "rejected"; reason: "invalid_title" | "invalid_due_at" };

export type ParsedSnooze =
  | { outcome: "ok"; value: { until: string } }
  | { outcome: "rejected"; reason: "invalid_until" };

const maxTitleLength = 120;
const isoInstant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isTitle(value: unknown): value is string {
  return typeof value === "string" && value.trim() !== "" && value.length <= maxTitleLength;
}

function isCalendarDay(text: string): boolean {
  const [year = 0, month = 0, day = 0] = text.slice(0, 10).split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

function isInstant(value: unknown): value is string {
  return (
    typeof value === "string" && isoInstant.test(value) && isCalendarDay(value) && !Number.isNaN(Date.parse(value))
  );
}

export function parseNewReminder(input: unknown): ParsedNewReminder {
  const { title, dueAt } = isRecord(input) ? input : {};
  if (!isTitle(title)) return { outcome: "rejected", reason: "invalid_title" };
  if (!isInstant(dueAt)) return { outcome: "rejected", reason: "invalid_due_at" };
  return { outcome: "ok", value: { title, dueAt } };
}

export function parseSnooze(input: unknown, now: Date): ParsedSnooze {
  const { until } = isRecord(input) ? input : {};
  if (!isInstant(until) || Date.parse(until) <= now.getTime()) {
    return { outcome: "rejected", reason: "invalid_until" };
  }
  return { outcome: "ok", value: { until } };
}

export function inSituation({ id, title, dueAt }: Reminder, situation: Situation): Reminder {
  return { id, title, dueAt, ...situation };
}

export function asOf(reminder: Reminder, now: Date): Reminder {
  switch (reminder.status) {
    case "open":
    case "done":
      return reminder;
    case "snoozed":
      return Date.parse(reminder.snoozedUntil) > now.getTime() ? reminder : inSituation(reminder, { status: "open" });
  }
}
