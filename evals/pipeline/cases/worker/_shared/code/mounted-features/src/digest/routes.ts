import type { Feature } from "../app.js";
import { ok, route } from "../kernel/http.js";

export const digestFeature: Feature = ({ store }) => [
  route("GET", "/digest", () => {
    const reminders = store.list();
    const open = reminders.filter((reminder) => reminder.status === "open").length;
    return ok(200, { open, done: reminders.length - open });
  }),
];
