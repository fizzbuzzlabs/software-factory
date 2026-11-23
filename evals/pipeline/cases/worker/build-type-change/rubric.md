one-situation: The reminder type models open, snoozed and done as alternatives of one value (for example a discriminated union), so the snooze end instant is a field of the snoozed alternative only.
no-bolt-on: The reminder type has no optional end-instant field sitting beside a status field shared by all reminders, and no boolean flag saying whether the reminder is snoozed.
one-clock-answer: One function or module decides whether a snoozed reminder still counts as snoozed against the clock; the list, the single read and the complete action do not each re-implement the comparison.
no-timer: Nothing uses setTimeout, setInterval or any background job to end a snooze.
