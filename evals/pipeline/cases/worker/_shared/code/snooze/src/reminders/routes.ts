import type { Clock } from "../kernel/clock.js";
import type { IdSource } from "../kernel/ids.js";
import { notFound, ok, queryOf, readJsonBody, rejected, route, type Reply, type Route } from "../kernel/http.js";
import { parseNewReminder, parseSnooze, type Reminder } from "./reminder.js";
import type { ReminderStore } from "./store.js";

function found(reminder: Reminder | undefined): Reply {
  return reminder === undefined ? notFound() : ok(200, reminder);
}

export function reminderRoutes(store: ReminderStore, clock: Clock, ids: IdSource): Route[] {
  return [
    route("POST", "/reminders", async (request) => {
      const body = await readJsonBody(request);
      if (body === undefined) return rejected(400, "malformed_json");
      const parsed = parseNewReminder(body);
      if (parsed.outcome === "rejected") return rejected(422, parsed.reason);
      const reminder: Reminder = { id: ids.next(), ...parsed.value, status: "open" };
      store.add(reminder);
      return ok(201, reminder);
    }),
    route("GET", "/reminders", (request) =>
      ok(200, store.list(queryOf(request).get("include") === "snoozed" ? "all" : "unsnoozed")),
    ),
    route("GET", "/reminders/:id", (_request, id) => found(store.get(id))),
    route("POST", "/reminders/:id/complete", (_request, id) => found(store.markDone(id))),
    route("POST", "/reminders/:id/snooze", async (request, id) => {
      const body = await readJsonBody(request);
      if (body === undefined) return rejected(400, "malformed_json");
      const reminder = store.get(id);
      if (reminder === undefined) return notFound();
      if (reminder.status === "done") return rejected(409, "already_done");
      const parsed = parseSnooze(body, clock.now());
      if (parsed.outcome === "rejected") return rejected(422, parsed.reason);
      return found(store.snooze(id, parsed.value.until));
    }),
  ];
}
