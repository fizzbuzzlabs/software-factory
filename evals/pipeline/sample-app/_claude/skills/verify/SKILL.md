---
name: verify
description: Verify a change to the reminders service at its real surface, by sending real HTTP requests to the booted service, and report one verdict - PASS, FAIL, SKIP or BLOCKED. Use for "/verify", "verify this change", or when a factory skill asks for the repo's verify over a tree and diff range.
argument-hint: "[<tree path>] [<diff range>] [<evidence ticket>]"
---

# Verify

Prove the change works in the running service. Passing tests are not the evidence: what the booted service answers is.

1. **Scope.** Take the diff range from the arguments, else `origin/main...HEAD`. If it changes nothing the service loads (only tests, `workflows/`, docs or tooling), the verdict is SKIP.
2. **Plan the requests.** From the ticket's `contract.md`, list the requests a caller would send to see each behavior the diff touches: the request that shows it working, and one for each way it can reject.
3. **Drive the real service.** Write the requests to a JSON file and run `npm run probe -- <file>`. The probe boots the service the way production does (`npm run start`, on a free port), sends each request in order and prints each response's status and body. The file is an array of steps:

   ```json
   [
     { "method": "POST", "path": "/reminders", "body": { "title": "Call the bank", "dueAt": "2031-05-01T09:00:00Z" } },
     { "path": "/reminders/{0.data.id}" },
     { "method": "POST", "path": "/reminders/{0.data.id}/complete", "waitMs": 1500 }
   ]
   ```

   `method` defaults to `GET`. `{N.a.b}` in a path is field `a.b` of step N's response. `waitMs` waits after the step, for behavior that depends on time passing.
4. **Judge.** Compare each response's status and JSON with what the contract says.

End with the verdict on its own line: `VERDICT: <PASS | FAIL | SKIP | BLOCKED> — <reason>`.

- **PASS** — every planned request answered as the contract says.
- **FAIL** — name the request and what came back instead.
- **BLOCKED** — the probe could not run or the service would not boot; quote the error. Say `port-busy` when the error is an address already in use.

Never return PASS from tests alone, and never put another check in the probe's place.
