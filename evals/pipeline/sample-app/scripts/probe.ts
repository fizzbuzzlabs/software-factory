import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { createInterface } from "node:readline";
import { setTimeout as wait } from "node:timers/promises";
import { stdoutLogger } from "../src/kernel/logger.js";

type Step = { method: string; path: string; body: unknown; waitMs: number };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toStep(value: unknown): Step {
  if (!isRecord(value) || typeof value.path !== "string") {
    throw new Error("each step needs a path");
  }
  return {
    method: typeof value.method === "string" ? value.method : "GET",
    path: value.path,
    body: value.body,
    waitMs: typeof value.waitMs === "number" ? value.waitMs : 0,
  };
}

function dig(value: unknown, keys: string[]): unknown {
  return keys.reduce<unknown>((current, key) => {
    if (Array.isArray(current)) return current[Number(key)];
    return isRecord(current) ? current[key] : undefined;
  }, value);
}

function fill(path: string, replies: unknown[]): string {
  return path.replace(/\{(\d+)\.([\w.]+)\}/g, (_match, index: string, pointer: string) => {
    const found = dig(replies[Number(index)], pointer.split("."));
    return typeof found === "string" || typeof found === "number" ? String(found) : "";
  });
}

function parseOrKeep(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

async function readSteps(file: string): Promise<Step[]> {
  const parsed: unknown = JSON.parse(await readFile(file, "utf8"));
  if (!Array.isArray(parsed)) throw new Error("the steps file holds a JSON array");
  return parsed.map(toStep);
}

async function send(baseUrl: string, step: Step, replies: unknown[]): Promise<void> {
  const path = fill(step.path, replies);
  const response = await fetch(`${baseUrl}${path}`, {
    method: step.method,
    ...(step.body === undefined ? {} : { body: JSON.stringify(step.body) }),
  });
  const reply = parseOrKeep(await response.text());
  replies.push(reply);
  stdoutLogger.log("probe_response", {
    step: replies.length - 1,
    request: `${step.method} ${path}`,
    status: response.status,
    body: JSON.stringify(reply),
  });
  if (step.waitMs > 0) await wait(step.waitMs);
}

async function main(): Promise<void> {
  const file = process.argv[2];
  if (file === undefined) throw new Error("usage: npm run probe -- <steps.json>");
  const steps = await readSteps(file);
  const service = spawn("npm", ["run", "--silent", "start"], {
    env: { ...process.env, PORT: "0" },
    stdio: ["ignore", "pipe", "inherit"],
  });
  try {
    const port = await new Promise<number>((resolve, reject) => {
      const lines = createInterface({ input: service.stdout });
      lines.on("line", (line) => {
        const match = /"event":"listening","port":(\d+)/.exec(line);
        if (match?.[1] !== undefined) resolve(Number(match[1]));
      });
      service.once("exit", (code) => {
        reject(new Error(`the service exited before listening, with code ${String(code)}`));
      });
    });
    const replies: unknown[] = [];
    for (const step of steps) {
      await send(`http://127.0.0.1:${String(port)}`, step, replies);
    }
  } finally {
    service.kill();
  }
}

await main();
