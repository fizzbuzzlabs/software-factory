import { once } from "node:events";
import type { Server } from "node:http";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createApp } from "../app.js";
import type { LogFields } from "../kernel/logger.js";
import { createReminderStore } from "./store.js";

const now = "2030-01-01T00:00:00.000Z";

let server: Server;
let baseUrl: string;
let logged: { event: string; fields: LogFields }[];
let nextId: () => string;

function sequentialIds(): () => string {
  let count = 0;
  return () => {
    count += 1;
    return `reminder-${String(count)}`;
  };
}

beforeEach(async () => {
  logged = [];
  nextId = sequentialIds();
  server = createApp({
    store: createReminderStore(),
    clock: { now: () => new Date(now) },
    ids: { next: () => nextId() },
    logger: { log: (event, fields) => logged.push({ event, fields }) },
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

function get(path: string): Promise<Response> {
  return fetch(`${baseUrl}${path}`);
}

function post(path: string, body?: unknown): Promise<Response> {
  return fetch(`${baseUrl}${path}`, { method: "POST", body: JSON.stringify(body) });
}

function postText(path: string, body: string): Promise<Response> {
  return fetch(`${baseUrl}${path}`, { method: "POST", body });
}

async function create(title: string, dueAt: string): Promise<void> {
  await post("/reminders", { title, dueAt });
}

describe("health", () => {
  it("reports that the service is up", async () => {
    const response = await get("/health");

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ data: { status: "ok" } });
  });
});

describe("creating a reminder", () => {
  it("creates an open reminder", async () => {
    const response = await post("/reminders", { title: "Call the dentist", dueAt: "2030-01-15T09:00:00Z" });

    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({
      data: { id: "reminder-1", title: "Call the dentist", dueAt: "2030-01-15T09:00:00Z", status: "open" },
    });
  });

  it("rejects a reminder whose title is empty", async () => {
    const response = await post("/reminders", { title: "", dueAt: "2030-01-15T09:00:00Z" });

    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ error: { reason: "invalid_title" } });
  });

  it("rejects a reminder whose due time is not an ISO instant", async () => {
    const response = await post("/reminders", { title: "Call the dentist", dueAt: "tomorrow" });

    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ error: { reason: "invalid_due_at" } });
  });

  it("stores nothing when a reminder is rejected", async () => {
    await post("/reminders", { title: "", dueAt: "2030-01-15T09:00:00Z" });

    expect(await (await get("/reminders")).json()).toEqual({ data: [] });
  });

  it.each([
    ["is not valid JSON", "{title:"],
    ["is empty", ""],
    ["is a JSON list", "[]"],
    ["is a JSON string", '"Call the dentist"'],
    ["is JSON null", "null"],
  ])("rejects a body that %s", async (_description, body) => {
    const response = await postText("/reminders", body);

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: { reason: "malformed_json" } });
  });
});

describe("listing reminders", () => {
  it("returns an empty list when there are no reminders", async () => {
    const response = await get("/reminders");

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ data: [] });
  });

  it("orders reminders by due time, earliest first", async () => {
    await create("Third", "2030-03-01T09:00:00Z");
    await create("First", "2030-01-01T09:00:00Z");
    await create("Second", "2030-02-01T09:00:00Z");

    const response = await get("/reminders");

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      data: [{ title: "First" }, { title: "Second" }, { title: "Third" }],
    });
  });

  it("compares due times as instants across offsets", async () => {
    await create("Later", "2030-01-01T09:00:00Z");
    await create("Earlier", "2030-01-01T10:00:00+02:00");

    expect(await (await get("/reminders")).json()).toMatchObject({
      data: [{ title: "Earlier" }, { title: "Later" }],
    });
  });

  it("orders reminders due at the same time by id", async () => {
    nextId = () => "b";
    await create("Created first", "2030-01-01T09:00:00Z");
    nextId = () => "a";
    await create("Created second", "2030-01-01T09:00:00Z");

    expect(await (await get("/reminders")).json()).toMatchObject({ data: [{ id: "a" }, { id: "b" }] });
  });
});

describe("fetching a reminder", () => {
  it("returns the reminder with that id", async () => {
    await create("Call the dentist", "2030-01-15T09:00:00Z");

    const response = await get("/reminders/reminder-1");

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      data: { id: "reminder-1", title: "Call the dentist", dueAt: "2030-01-15T09:00:00Z", status: "open" },
    });
  });

  it("answers not found for an id that does not exist", async () => {
    const response = await get("/reminders/missing");

    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ error: { reason: "not_found" } });
  });
});

describe("completing a reminder", () => {
  it("marks the reminder done", async () => {
    await create("Call the dentist", "2030-01-15T09:00:00Z");

    const response = await post("/reminders/reminder-1/complete");

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      data: { id: "reminder-1", title: "Call the dentist", dueAt: "2030-01-15T09:00:00Z", status: "done" },
    });
    expect(await (await get("/reminders/reminder-1")).json()).toMatchObject({ data: { status: "done" } });
  });

  it("leaves a reminder done when it is completed again", async () => {
    await create("Call the dentist", "2030-01-15T09:00:00Z");
    await post("/reminders/reminder-1/complete");

    const response = await post("/reminders/reminder-1/complete");

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ data: { id: "reminder-1", status: "done" } });
  });

  it("answers not found for an id that does not exist", async () => {
    const response = await post("/reminders/missing/complete");

    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ error: { reason: "not_found" } });
  });
});

describe("requests outside the API", () => {
  it("answers not found for an unknown path", async () => {
    const response = await get("/nowhere");

    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ error: { reason: "not_found" } });
  });

  it.each([
    ["POST", "/health"],
    ["DELETE", "/reminders"],
    ["PUT", "/reminders/reminder-1"],
    ["GET", "/reminders/reminder-1/complete"],
  ])("rejects %s on %s as a method that is not allowed", async (method, path) => {
    const response = await fetch(`${baseUrl}${path}`, { method });

    expect(response.status).toBe(405);
    expect(await response.json()).toEqual({ error: { reason: "method_not_allowed" } });
  });
});

describe("logging", () => {
  it("logs a rejection once with its reason code", async () => {
    await post("/reminders", { title: "", dueAt: "2030-01-15T09:00:00Z" });

    expect(logged).toEqual([
      {
        event: "request_rejected",
        fields: { at: now, method: "POST", path: "/reminders", status: 422, reason: "invalid_title" },
      },
    ]);
  });

  it.each([
    ["malformed_json", "POST", "/reminders", "{"],
    ["invalid_due_at", "POST", "/reminders", '{"title":"Call the dentist"}'],
    ["not_found", "GET", "/reminders/missing", undefined],
    ["not_found", "GET", "/nowhere", undefined],
    ["method_not_allowed", "DELETE", "/reminders", undefined],
  ])("logs %s for %s %s", async (reason, method, path, body) => {
    await fetch(`${baseUrl}${path}`, { method, ...(body === undefined ? {} : { body }) });

    expect(logged.map((entry) => entry.fields.reason)).toEqual([reason]);
  });

  it("logs nothing for requests that succeed", async () => {
    await create("Call the dentist", "2030-01-15T09:00:00Z");
    await get("/reminders");
    await get("/health");

    expect(logged).toEqual([]);
  });
});

describe("unexpected failures", () => {
  it("answers with an internal error and logs it when a dependency throws", async () => {
    nextId = () => {
      throw new Error("no ids left");
    };

    const response = await post("/reminders", { title: "Call the dentist", dueAt: "2030-01-15T09:00:00Z" });

    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({ error: { reason: "internal_error" } });
    expect(logged).toMatchObject([{ event: "request_failed", fields: { status: 500, reason: "internal_error" } }]);
  });
});
