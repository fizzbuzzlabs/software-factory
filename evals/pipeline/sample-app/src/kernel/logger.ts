export type LogFields = Record<string, string | number>;

export type Logger = { log(event: string, fields: LogFields): void };

export const stdoutLogger: Logger = {
  log(event, fields) {
    process.stdout.write(`${JSON.stringify({ event, ...fields })}\n`);
  },
};
