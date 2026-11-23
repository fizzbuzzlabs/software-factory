"""A JSON state file shared by a fake server and the graders, plus an append-only call log."""

import contextlib
import fcntl
import json
import os
import time


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".%03dZ" % (int(time.time() * 1000) % 1000)


class Store:
    def __init__(self, state_path, calls_path):
        self.state_path = state_path
        self.calls_path = calls_path
        self.lock_path = state_path + ".lock"

    @contextlib.contextmanager
    def locked(self):
        with open(self.lock_path, "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def read(self):
        with open(self.state_path) as handle:
            return json.load(handle)

    def write(self, state):
        temporary = self.state_path + ".tmp"
        with open(temporary, "w") as handle:
            json.dump(state, handle, indent=1)
        os.replace(temporary, self.state_path)

    def log(self, tool, arguments, error=None):
        entry = {"at": now(), "epoch": time.time(), "tool": tool, "arguments": arguments}
        if error:
            entry["error"] = error
        with open(self.calls_path, "a") as handle:
            handle.write(json.dumps(entry) + "\n")
