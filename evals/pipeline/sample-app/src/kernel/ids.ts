import { randomUUID } from "node:crypto";

export type IdSource = { next(): string };

export const randomIds: IdSource = { next: () => randomUUID() };
