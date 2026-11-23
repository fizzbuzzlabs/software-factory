# reminders

A small HTTP service that keeps reminders in memory. See `README.md` for the API, the layout and
the checks.

**Linear team:** Acme

GitHub repository: `acme-labs/reminders` (the `origin` remote).

## Working here

- `npm ci` first. Then `npm run typecheck`, `npm run lint`, `npm test` and `npm run debt:check`
  are the checks CI runs on every pull request.
- `npm run probe -- <steps.json>` boots the service the way production does and sends it real
  requests. The `verify` skill uses it.
- Code is grouped by feature under `src/`; `src/kernel/` holds what every feature shares.
- Each ticket's spec, design, contract and test plan live in `workflows/<date>-<ticket>-<slug>/`.
