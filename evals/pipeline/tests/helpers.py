import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))


def call(server, env, name, arguments):
    """Start a fake MCP server, make one tool call, and return (is error, parsed result or text)."""
    lines = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
    ]
    done = subprocess.run([sys.executable, os.path.join(ROOT, "fakes", server)],
                          input="".join(json.dumps(line) + "\n" for line in lines),
                          capture_output=True, text=True, env=dict(os.environ, **env))
    reply = json.loads(done.stdout.splitlines()[-1])["result"]
    text = reply["content"][0]["text"]
    try:
        return reply["isError"], json.loads(text)
    except ValueError:
        return reply["isError"], text
