import { describe, expect, it } from "vitest";
import { checkBody } from "./body.js";

const title = "Call the dentist";
const dueAt = "2030-01-15T09:00:00Z";

describe("checking the body of a new reminder", () => {
  it("accepts a title with an ISO instant", () => {
    expect(checkBody({ title, dueAt })).toEqual({ outcome: "ok", value: { title, dueAt } });
  });

  it("keeps only the title and the due time", () => {
    expect(checkBody({ title, dueAt, status: "done", id: "chosen" })).toEqual({
      outcome: "ok",
      value: { title, dueAt },
    });
  });

  it("accepts a title of exactly 120 characters", () => {
    expect(checkBody({ title: "a".repeat(120), dueAt }).outcome).toBe("ok");
  });

  it.each([
    ["a UTC instant with fractional seconds", "2030-01-15T09:00:00.250Z"],
    ["an instant with a positive offset", "2030-01-15T09:00:00+02:00"],
    ["an instant with a negative offset", "2030-01-15T09:00:00-05:30"],
    ["an instant without seconds", "2030-01-15T09:00Z"],
  ])("accepts a due time that is %s", (_description, value) => {
    expect(checkBody({ title, dueAt: value }).outcome).toBe("ok");
  });

  it.each([
    ["missing", { dueAt }],
    ["not a string", { title: 42, dueAt }],
    ["empty", { title: "", dueAt }],
    ["only whitespace", { title: " \t\n", dueAt }],
    ["longer than 120 characters", { title: "a".repeat(121), dueAt }],
  ])("rejects a reminder whose title is %s", (_description, input) => {
    expect(checkBody(input)).toEqual({ outcome: "rejected", reason: "invalid_title" });
  });

  it.each([
    ["missing", { title }],
    ["not a string", { title, dueAt: 1894352400000 }],
    ["empty", { title, dueAt: "" }],
    ["a date without a time", { title, dueAt: "2030-01-15" }],
    ["a time without a zone", { title, dueAt: "2030-01-15T09:00:00" }],
    ["in a month that does not exist", { title, dueAt: "2030-13-15T09:00:00Z" }],
    ["on a day that does not exist", { title, dueAt: "2030-02-30T09:00:00Z" }],
    ["at an hour that does not exist", { title, dueAt: "2030-01-15T25:00:00Z" }],
    ["not a date at all", { title, dueAt: "next tuesday" }],
  ])("rejects a reminder whose due time is %s", (_description, input) => {
    expect(checkBody(input)).toEqual({ outcome: "rejected", reason: "invalid_due_at" });
  });

  it("reports the title when both the title and the due time are invalid", () => {
    expect(checkBody({ title: "", dueAt: "soon" })).toEqual({
      outcome: "rejected",
      reason: "invalid_title",
    });
  });

  it.each([
    ["null", null],
    ["a string", "Call the dentist"],
    ["a list", [title, dueAt]],
  ])("rejects input that is %s", (_description, input) => {
    expect(checkBody(input).outcome).toBe("rejected");
  });
});
