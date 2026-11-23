import { once } from "node:events";
import type { Server } from "node:http";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createApp } from "../app.js";
import { createReminderStore } from "../reminders/store.js";

let server: Server;
let baseUrl: string;

function sequentialIds(): () => string {
  let count = 0;
  return () => {
    count += 1;
    return `reminder-${String(count)}`;
  };
}

beforeEach(async () => {
  server = createApp({
    store: createReminderStore(),
    clock: { now: () => new Date("2030-01-01T00:00:00.000Z") },
    ids: { next: sequentialIds() },
    logger: { log: () => undefined },
  });
  server.listen(0);
  await once(server, "listening");
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("the server is not listening on a TCP port");
  }
  baseUrl = `http://127.0.0.1:${String(address.port)}`;
});

afterEach(async () => {
  server.close();
  await once(server, "close");
});

function post(path: string, body?: unknown): Promise<Response> {
  return fetch(`${baseUrl}${path}`, { method: "POST", body: JSON.stringify(body) });
}

describe("the digest", () => {
  it("counts the open and the done reminders", async () => {
    await post("/reminders", { title: "Call the dentist", dueAt: "2030-01-15T09:00:00Z" });
    await post("/reminders", { title: "Water the plants", dueAt: "2030-01-16T09:00:00Z" });
    await post("/reminders", { title: "Renew the passport", dueAt: "2030-01-17T09:00:00Z" });
    await post("/reminders/reminder-1/complete");

    const response = await fetch(`${baseUrl}/digest`);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ data: { open: 2, done: 1 } });
  });

  it("counts nothing when there are no reminders", async () => {
    const response = await fetch(`${baseUrl}/digest`);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ data: { open: 0, done: 0 } });
  });
});
