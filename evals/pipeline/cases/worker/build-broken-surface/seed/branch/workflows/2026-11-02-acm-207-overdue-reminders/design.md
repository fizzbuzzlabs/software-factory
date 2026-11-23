# Design: Overdue reminders

**Project:** 2026-11-02-acm-207-overdue-reminders

## Key decisions

1. **Overdue is its own feature, beside reminders and the digest.** It reads reminders and the
   clock and owns one question. It gets its own folder and its own route, like the digest.
   - Alternative considered: another query option on the reminder list. Rejected: the list's
     options describe which reminders, not what time it is.
2. **Overdue is decided when asked**, by comparing each open reminder's due instant with the
   injected clock.
