# Reject reminders due in the past

**Source:** https://linear.app/acme/issue/ACM-206
**Created:** 2026-11-02

## Problem

The app accepts a reminder whose due time has already passed. It is always a typo (last year's
date, AM for PM) and the person finds out only when nothing reminds them.

## Requirements

### Must have

1. Creating a reminder whose due time is earlier than now is rejected with its own reason code,
   and nothing is stored.
2. A reminder due now or later is accepted as today.

### Won't have

- Any change to existing reminders whose due time has since passed.

## Success Criteria

- Create a reminder due yesterday → rejected with a reason code; the list is unchanged.
- Create a reminder due tomorrow → created.
