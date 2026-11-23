# Rename a reminder

**Source:** https://linear.app/acme/issue/__TICKET__
**Created:** 2026-11-02

## Problem

A reminder's title can't be changed after it is created. People fix a typo by deleting nothing
(there is no delete) and creating a second reminder, so lists fill with near-duplicates.

## Requirements

### Must have

1. A person can change the title of an existing reminder. Nothing else about it changes.
2. A new title is held to the same rules as a title at creation.
3. Renaming a reminder that doesn't exist answers the way every other missing reminder does.

### Won't have

- Changing the due time or the status through a rename.
- A history of old titles.

## Success Criteria

- Rename a reminder → reading it back, alone or in the list, shows the new title; id, due time and status are as before.
- Rename to an empty title → rejected with the reason code creation uses; the old title stays.
- Rename a missing reminder → not found.
