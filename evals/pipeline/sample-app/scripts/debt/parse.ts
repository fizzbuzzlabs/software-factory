export type JsonRecord = Record<string, unknown>;

export function record(value: unknown, what: string): JsonRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`[debt] expected ${what} to be an object`);
  }
  return { ...value };
}

export function list(value: unknown, what: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new Error(`[debt] expected ${what} to be a list`);
  }
  const items: unknown[] = value;
  return items;
}

export function text(value: unknown, what: string): string {
  if (typeof value !== "string") {
    throw new Error(`[debt] expected ${what} to be a string`);
  }
  return value;
}

export function count(value: unknown, what: string): number {
  if (typeof value !== "number") {
    throw new Error(`[debt] expected ${what} to be a number`);
  }
  return value;
}
