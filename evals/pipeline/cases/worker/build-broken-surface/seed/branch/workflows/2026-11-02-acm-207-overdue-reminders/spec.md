# Overdue reminders

**Source:** https://linear.app/acme/issue/ACM-207
**Created:** 2026-11-02

## Problem

People open the app to find out what they have missed, and have to read the whole list and compare
every due time with the clock themselves.

## Requirements

### Must have

1. One request returns the reminders that are still open and whose due time has passed, oldest
   first.
2. A reminder that is done is never overdue.

### Won't have

- Notifications, or any change to the existing list.

## Success Criteria

- An open reminder whose due time has passed shows up as overdue; one due tomorrow does not.
- Completing an overdue reminder takes it out.
