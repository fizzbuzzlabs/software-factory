export type Reminder = {
  id: string;
  title: string;
  dueAt: string;
  status: "open" | "done";
};

type NewReminder = Pick<Reminder, "title" | "dueAt">;

type ParsedTitle = { outcome: "ok"; value: string } | { outcome: "rejected"; reason: "invalid_title" };

export type ParsedNewReminder =
  | { outcome: "ok"; value: NewReminder }
  | { outcome: "rejected"; reason: "invalid_title" | "invalid_due_at" };

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

export function parseTitle(input: unknown): ParsedTitle {
  const { title } = isRecord(input) ? input : {};
  if (!isTitle(title)) return { outcome: "rejected", reason: "invalid_title" };
  return { outcome: "ok", value: title };
}

export function parseNewReminder(input: unknown): ParsedNewReminder {
  const title = parseTitle(input);
  if (title.outcome === "rejected") return title;
  const { dueAt } = isRecord(input) ? input : {};
  if (!isInstant(dueAt)) return { outcome: "rejected", reason: "invalid_due_at" };
  return { outcome: "ok", value: { title: title.value, dueAt } };
}
