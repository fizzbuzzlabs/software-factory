import { createServer, type IncomingMessage, type Server } from "node:http";
import type { Clock } from "./kernel/clock.js";
import { createRouter, ok, pathOf, route, sendJson, type Route } from "./kernel/http.js";
import type { IdSource } from "./kernel/ids.js";
import type { Logger } from "./kernel/logger.js";
import type { ReminderStore } from "./reminders/store.js";

type AppDeps = {
  store: ReminderStore;
  clock: Clock;
  ids: IdSource;
  logger: Logger;
};

export type Feature = (deps: AppDeps) => Route[];

export function createApp(deps: AppDeps, features: Feature[]): Server {
  const { clock, logger } = deps;
  const dispatch = createRouter([
    route("GET", "/health", () => ok(200, { status: "ok" })),
    ...features.flatMap((feature) => feature(deps)),
  ]);
  const requestFields = (request: IncomingMessage) => ({
    at: clock.now().toISOString(),
    method: request.method ?? "",
    path: pathOf(request),
  });

  return createServer((request, response) => {
    dispatch(request).then(
      (reply) => {
        if (reply.outcome === "ok") {
          sendJson(response, reply.status, { data: reply.data });
          return;
        }
        logger.log("request_rejected", { ...requestFields(request), status: reply.status, reason: reply.reason });
        sendJson(response, reply.status, { error: { reason: reply.reason } });
      },
      (error: unknown) => {
        const reason = "internal_error";
        const message = error instanceof Error ? error.message : String(error);
        logger.log("request_failed", { ...requestFields(request), status: 500, reason, message });
        sendJson(response, 500, { error: { reason } });
      },
    );
  });
}
