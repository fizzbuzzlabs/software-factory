import { describe, expect, it } from "vitest";
import { parseNewReminder, parseSnooze } from "./reminder.js";

const title = "Call the dentist";
const dueAt = "2030-01-15T09:00:00Z";

describe("parsing a new reminder", () => {
  it("accepts a title with an ISO instant", () => {
    expect(parseNewReminder({ title, dueAt })).toEqual({ outcome: "ok", value: { title, dueAt } });
  });

  it("keeps only the title and the due time", () => {
    expect(parseNewReminder({ title, dueAt, status: "done", id: "chosen" })).toEqual({
      outcome: "ok",
      value: { title, dueAt },
    });
  });

  it("accepts a title of exactly 120 characters", () => {
    expect(parseNewReminder({ title: "a".repeat(120), dueAt }).outcome).toBe("ok");
  });

  it.each([
    ["a UTC instant with fractional seconds", "2030-01-15T09:00:00.250Z"],
    ["an instant with a positive offset", "2030-01-15T09:00:00+02:00"],
    ["an instant with a negative offset", "2030-01-15T09:00:00-05:30"],
    ["an instant without seconds", "2030-01-15T09:00Z"],
  ])("accepts a due time that is %s", (_description, value) => {
    expect(parseNewReminder({ title, dueAt: value }).outcome).toBe("ok");
  });

  it.each([
    ["missing", { dueAt }],
    ["not a string", { title: 42, dueAt }],
    ["empty", { title: "", dueAt }],
    ["only whitespace", { title: " \t\n", dueAt }],
    ["longer than 120 characters", { title: "a".repeat(121), dueAt }],
  ])("rejects a reminder whose title is %s", (_description, input) => {
    expect(parseNewReminder(input)).toEqual({ outcome: "rejected", reason: "invalid_title" });
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
    expect(parseNewReminder(input)).toEqual({ outcome: "rejected", reason: "invalid_due_at" });
  });

  it("reports the title when both the title and the due time are invalid", () => {
    expect(parseNewReminder({ title: "", dueAt: "soon" })).toEqual({
      outcome: "rejected",
      reason: "invalid_title",
    });
  });

  it.each([
    ["null", null],
    ["a string", "Call the dentist"],
    ["a list", [title, dueAt]],
  ])("rejects input that is %s", (_description, input) => {
    expect(parseNewReminder(input).outcome).toBe("rejected");
  });
});

describe("parsing a snooze request", () => {
  const now = new Date("2030-01-01T12:00:00Z");

  it("accepts an instant after now", () => {
    expect(parseSnooze({ until: "2030-01-01T12:00:01Z" }, now)).toEqual({
      outcome: "ok",
      value: { until: "2030-01-01T12:00:01Z" },
    });
  });

  it("keeps only the instant", () => {
    expect(parseSnooze({ until: "2030-01-02T09:00:00Z", status: "done", id: "chosen" }, now)).toEqual({
      outcome: "ok",
      value: { until: "2030-01-02T09:00:00Z" },
    });
  });

  it("accepts an instant that is after now once its offset is applied", () => {
    expect(parseSnooze({ until: "2030-01-01T11:30:00-01:00" }, now).outcome).toBe("ok");
  });

  it.each([
    ["missing", {}],
    ["not a string", { until: 1893499201000 }],
    ["empty", { until: "" }],
    ["a date without a time", { until: "2030-01-02" }],
    ["a time without a zone", { until: "2030-01-02T09:00:00" }],
    ["not a date at all", { until: "after lunch" }],
    ["before now", { until: "2030-01-01T11:59:59Z" }],
    ["before now once its offset is applied", { until: "2030-01-01T12:30:00+01:00" }],
    ["exactly now", { until: "2030-01-01T12:00:00Z" }],
  ])("rejects a snooze whose instant is %s", (_description, input) => {
    expect(parseSnooze(input, now)).toEqual({ outcome: "rejected", reason: "invalid_until" });
  });

  it.each([
    ["null", null],
    ["a string", "2030-01-02T09:00:00Z"],
    ["a list", ["2030-01-02T09:00:00Z"]],
  ])("rejects input that is %s", (_description, input) => {
    expect(parseSnooze(input, now)).toEqual({ outcome: "rejected", reason: "invalid_until" });
  });
});
