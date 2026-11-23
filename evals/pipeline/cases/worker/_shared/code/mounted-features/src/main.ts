import { createApp } from "./app.js";
import { digestFeature } from "./digest/routes.js";
import { systemClock } from "./kernel/clock.js";
import { randomIds } from "./kernel/ids.js";
import { stdoutLogger } from "./kernel/logger.js";
import { remindersFeature } from "./reminders/routes.js";
import { createReminderStore } from "./reminders/store.js";

const server = createApp(
  {
    store: createReminderStore(),
    clock: systemClock,
    ids: randomIds,
    logger: stdoutLogger,
  },
  [remindersFeature, digestFeature],
);

server.listen(Number(process.env.PORT ?? 0), () => {
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("the server is not listening on a TCP port");
  }
  stdoutLogger.log("listening", { port: address.port });
});
