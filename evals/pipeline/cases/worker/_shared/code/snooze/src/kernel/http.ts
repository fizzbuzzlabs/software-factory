import type { IncomingMessage, ServerResponse } from "node:http";
import { text } from "node:stream/consumers";

type Envelope = { data: unknown } | { error: { reason: string } };

export type Reply =
  | { outcome: "ok"; status: number; data: unknown }
  | { outcome: "rejected"; status: number; reason: string };

type Handler = (request: IncomingMessage, ...captures: string[]) => Reply | Promise<Reply>;

export type Route = {
  method: string;
  capture(path: string): string[] | undefined;
  handle: Handler;
};

export function ok(status: number, data: unknown): Reply {
  return { outcome: "ok", status, data };
}

export function rejected(status: number, reason: string): Reply {
  return { outcome: "rejected", status, reason };
}

export function notFound(): Reply {
  return rejected(404, "not_found");
}

export function route(method: string, pattern: string, handle: Handler): Route {
  const matcher = new RegExp(`^${pattern.replace(/:\w+/g, "([^/]+)")}$`);
  return { method, capture: (path) => matcher.exec(path)?.slice(1), handle };
}

export function pathOf(request: IncomingMessage): string {
  const [path = ""] = (request.url ?? "").split("?");
  return path;
}

export function queryOf(request: IncomingMessage): URLSearchParams {
  const [, query = ""] = (request.url ?? "").split("?");
  return new URLSearchParams(query);
}

export function createRouter(routes: Route[]): (request: IncomingMessage) => Promise<Reply> {
  return async (request) => {
    const path = pathOf(request);
    const onPath = routes.flatMap((candidate) => {
      const captures = candidate.capture(path);
      return captures === undefined ? [] : [{ route: candidate, captures }];
    });
    if (onPath.length === 0) return notFound();
    const match = onPath.find((candidate) => candidate.route.method === request.method);
    if (match === undefined) return rejected(405, "method_not_allowed");
    return match.route.handle(request, ...match.captures);
  };
}

export async function readJsonBody(request: IncomingMessage): Promise<object | undefined> {
  const raw = await text(request);
  try {
    const value: unknown = JSON.parse(raw);
    return typeof value === "object" && value !== null && !Array.isArray(value) ? value : undefined;
  } catch {
    return undefined;
  }
}

export function sendJson(response: ServerResponse, status: number, body: Envelope): void {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(payload),
  });
  response.end(payload);
}
