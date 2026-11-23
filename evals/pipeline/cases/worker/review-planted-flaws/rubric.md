repeat-cut: The contract no longer has a behavior or option for a repeat interval or any recurring snooze.
env-option-cut: The contract no longer has the MAX_SNOOZE_DAYS setting or any other option that no production caller sets.
bolt-on-fixed: The reminder type is no longer described as status plus an optional snoozedUntil and an isSnoozed flag; the Modules section says the type is rebuilt or extended so that the snooze end time exists only in the snoozed state.
risk-first: The first behavior is an end-to-end proof of the riskiest assumption (a snooze taking effect through the HTTP surface, or ending by itself), not the health endpoint or another trivial step.
done-reminder-added: The contract has a behavior (or anti-behavior) saying a reminder that is already done cannot be snoozed, with a reason the caller sees.
own-module-mock-cut: No testing decision mocks the app's own store module; rejections are tested through the real surface with injected fakes.
prose-assertion-cut: No testing decision asserts on message wording; rejections are checked by status and reason code.
kept-what-held: The behaviors that were already sound (snooze an open reminder, reject a non-future time, default list hides snoozed, missing reminder, snooze ends by itself, complete a snoozed reminder) are still present.
