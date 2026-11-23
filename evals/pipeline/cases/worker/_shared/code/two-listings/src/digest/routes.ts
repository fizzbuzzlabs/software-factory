import { ok, route, type Route } from "../kernel/http.js";
import type { ReminderStore } from "../reminders/store.js";

export function digestRoutes(store: ReminderStore): Route[] {
  return [
    route("GET", "/digest", () =>
      ok(200, {
        open: store.listOpen().length,
        done: store.listAll().filter(({ status }) => status === "done").length,
      }),
    ),
  ];
}
