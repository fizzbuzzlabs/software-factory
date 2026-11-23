# reminders

A small HTTP service that keeps reminders in memory. Node 22, TypeScript, `node:http`, no framework.

## Run

```bash
npm ci
npm run start          # PORT=8080 npm run start to pick the port
npm run probe -- steps.json   # boot the service on a free port and send it the requests in steps.json
```

With `PORT` unset or `0` the service listens on a free port. Once it is listening it logs one line,
`{"event":"listening","port":<n>}`.

## API

Every response body is an envelope: `{ "data": ... }` on success, `{ "error": { "reason": "<code>" } }`
on failure.

A reminder is `{ id, title, dueAt, status }`. `dueAt` is an ISO-8601 instant such as
`2030-01-15T09:00:00Z` or `2030-01-15T09:00:00+02:00`. `status` is `open` or `done`.

| Request | Success | Failure |
|---|---|---|
| `GET /health` | 200 `{ status: "ok" }` | |
| `POST /reminders` with `{ title, dueAt }` | 201, the reminder, `open` | 400 `malformed_json`, 422 `invalid_title`, 422 `invalid_due_at` |
| `GET /reminders` | 200, every reminder by `dueAt`, then by `id` | |
| `GET /reminders/:id` | 200, the reminder | 404 `not_found` |
| `POST /reminders/:id/complete` | 200, the reminder, `done` | 404 `not_found` |
| `GET /digest` | 200 `{ open, done }`, how many reminders are open and how many are done | |

- `malformed_json`: the body is not valid JSON, or is not a JSON object.
- `invalid_title`: the title is missing, not a string, blank, or longer than 120 characters.
- `invalid_due_at`: the due time is missing, not a string, or not an ISO-8601 instant.
- An unknown path answers 404 `not_found`. A known path with the wrong method answers 405
  `method_not_allowed`. An unexpected failure answers 500 `internal_error`.

Every 4xx is logged once as a `request_rejected` line that carries its reason code.

## Layout

Code is grouped by feature. `src/kernel/` holds what every feature shares. A feature is a function
from the app's dependencies to its routes, and the features the service serves are mounted in
`src/main.ts`.

```
src/main.ts                 boot: build the real dependencies, mount the features and listen
src/app.ts                  createApp(deps, features): the server, given { store, clock, ids, logger }
                            and the features to mount
src/kernel/logger.ts        the one logger, JSON lines on stdout
src/kernel/http.ts          routes, replies, reading and sending JSON
src/kernel/clock.ts         Clock and the system clock
src/kernel/ids.ts           IdSource and random ids
src/reminders/reminder.ts   Reminder, and parseNewReminder for untrusted input
src/reminders/store.ts      the in-memory store
src/reminders/routes.ts     the reminders feature
src/digest/routes.ts        the digest feature
```

Tests sit beside the code. `*.http.test.ts` files start the app on a free port with a fake clock,
fake ids and a fake logger, and call it with `fetch`.

## Checks

```bash
npm run typecheck     # tsc, strict
npm run lint          # eslint with zero warnings, then the no-comments check
npm test              # vitest
npm run debt:check    # duplication and import cycles against debt-baseline.json
```

- **ESLint** (`eslint.config.ts`, `tsconfig.principles.json`): type-aware, no type assertions, no
  `any`, no floating promises, exhaustive switches. Only `src/kernel/logger.ts` may write to stdout.
- **No comments** (`controls/no-comments/`): code and tests carry no comments, and test titles carry
  no ticket ids. `npm run lint:comments` runs it alone.
- **Debt ratchet** (`scripts/debt/`, `knip.json`): `npm run debt` writes `reports/debt/`.
  `npm run debt:baseline:update` is the only way to move `debt-baseline.json`.
