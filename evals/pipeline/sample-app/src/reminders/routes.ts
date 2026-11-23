import type { IdSource } from "../kernel/ids.js";
import { notFound, ok, readJsonBody, rejected, route, type Reply, type Route } from "../kernel/http.js";
import { parseNewReminder, type Reminder } from "./reminder.js";
import type { ReminderStore } from "./store.js";

function found(reminder: Reminder | undefined): Reply {
  return reminder === undefined ? notFound() : ok(200, reminder);
}

export function reminderRoutes(store: ReminderStore, ids: IdSource): Route[] {
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
    route("GET", "/reminders", () => ok(200, store.list())),
    route("GET", "/reminders/:id", (_request, id) => found(store.get(id))),
    route("POST", "/reminders/:id/complete", (_request, id) => found(store.markDone(id))),
  ];
}
