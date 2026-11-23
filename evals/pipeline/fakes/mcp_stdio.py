"""Minimal MCP server over stdio (newline-delimited JSON-RPC 2.0), stdlib only.

A fake registers tools as (name, description, input schema, handler). A handler takes the
call's arguments dict and returns a JSON-serialisable value, or raises ToolError to return
an error result the way a real server reports a failed call.
"""

import json
import sys


class ToolError(Exception):
    pass


class Server:
    def __init__(self, name):
        self.name = name
        self.tools = {}

    def tool(self, name, description, properties=None, required=None):
        def register(handler):
            self.tools[name] = {
                "handler": handler,
                "spec": {
                    "name": name,
                    "description": description,
                    "inputSchema": {
                        "type": "object",
                        "properties": properties or {},
                        "required": required or [],
                    },
                },
            }
            return handler

        return register

    def call(self, name, arguments):
        entry = self.tools.get(name)
        if entry is None:
            return {"content": [{"type": "text", "text": "Unknown tool: " + name}], "isError": True}
        try:
            value = entry["handler"](arguments or {})
        except ToolError as error:
            return {"content": [{"type": "text", "text": str(error)}], "isError": True}
        except (KeyError, TypeError, ValueError, IndexError) as error:
            text = "Invalid arguments for tool %s: %r" % (name, error)
            return {"content": [{"type": "text", "text": text}], "isError": True}
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    def handle(self, message):
        method = message.get("method")
        params = message.get("params") or {}
        if method == "initialize":
            return {
                "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": self.name, "version": "0.0.1"},
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [entry["spec"] for entry in self.tools.values()]}
        if method == "tools/call":
            return self.call(params.get("name", ""), params.get("arguments"))
        return None

    def serve(self):
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if "id" not in message:
                continue
            result = self.handle(message)
            if result is None:
                reply = {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "error": {"code": -32601, "message": "Method not found"},
                }
            else:
                reply = {"jsonrpc": "2.0", "id": message["id"], "result": result}
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
