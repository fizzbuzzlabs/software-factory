# Design: Rename a reminder

**Project:** __FOLDER__

## Key decisions

1. **One action on an existing reminder**, `PATCH /reminders/:id`, carrying only the new title.
2. **The title rules have one owner.** Creation already decides what a title may be; renaming asks
   the same owner, so the two can't drift apart.
   - Alternative considered: validate in the rename handler. Rejected: a second copy of the rules.
3. **Rejections follow the existing pattern:** a status code and a reason code in the envelope,
   logged once.

## Boundaries

- A rename changes the title and nothing else.
