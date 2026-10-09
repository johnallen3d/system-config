#!/usr/bin/env python3
"""Isolated actual-CLIProxyAPI tests against a loopback mock; no provider/model calls.

Run on Omarchy with its manager's Python (PyYAML) and installed cliproxyapi.
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "modules/home-manager/subscription-proxy"))
spec = importlib.util.spec_from_file_location("manager", ROOT / "modules/home-manager/subscription-proxy/manager.py")
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    binary = shutil.which("cliproxyapi")
    assert binary, "Requires the installed pinned proxy binary"
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((dict(self.headers), data))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            chunks = [
                {"id": "mock", "object": "chat.completion.chunk", "created": 1, "model": "glm-5.2",
                 "choices": [{"index": 0, "delta": {"role": "assistant", "tool_calls": [{
                     "index": 0, "id": "call_test", "type": "function", "function": {
                         "name": "probe", "arguments": '{"value":"OK"}'}}]}, "finish_reason": None}]},
                {"id": "mock", "object": "chat.completion.chunk", "created": 1, "model": "glm-5.2",
                 "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                 "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
            ]
            for chunk in chunks:
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix="subscription-proxy-protocol-") as tmp, patch.dict(os.environ, HOME=tmp):
            home = Path(tmp)
            manager.ROOT = home / ".config/subscription-proxy"
            personal, work = port(), port()
            template = home / "template.json"
            manager.private_json(template, {"host": "127.0.0.1", "ports": {"personal": personal, "work": work}})
            manager.private_json(manager.ROOT / "endpoints.json", {
                "personal": f"http://127.0.0.1:{personal}", "work": f"http://127.0.0.1:{work}"})
            with contextlib.redirect_stdout(io.StringIO()):
                manager.seed_server(template)
            process = subprocess.Popen([binary, "--config", str(manager.ROOT / "server-work.yaml"), "--local-model"],
                                       env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.time() + 15
            while True:
                try:
                    manager.request("work", "/config")
                    break
                except ValueError:
                    if time.time() > deadline or process.poll() is not None:
                        raise AssertionError("Isolated proxy failed startup") from None
                    time.sleep(0.2)
            assert manager.go_ready() is False, "Absent optional v8 nodes must not break status"
            providers = manager.go_providers()
            assert providers[0]["name"] == "opencode-go"
            assert providers[0]["base-url"] == "https://opencode.ai/zen/go/v1"
            # Exercise the same configuration API used by the official panel.
            providers[0]["keys"] = [{"api-key": "synthetic-upstream-key"}]
            manager.request("work", "/config", "PATCH", {"api-keys": {"openai-compatibility": providers}})
            assert manager.go_ready() is True
            # Replace ONLY this test's upstream with a loopback mock before making a request.
            providers[0]["base-url"] = f"http://127.0.0.1:{upstream.server_port}/v1"
            manager.request("work", "/config", "PATCH", {"api-keys": {"openai-compatibility": providers}})
            for provider in ("codex", "claude"):
                result = manager.request("work", "/oauth/auth-url?provider=" + provider)
                assert result["url"].startswith("https://") and result["state"]
                manager.request("work", "/oauth/session?state=" + result["state"], "DELETE")
            print("PASS actual 8.0.23: v8 empty-config handling, Go key update/readiness, and central Codex/Claude OAuth start/cancel routes")
            key = manager.credentials()["work"]["client"]
            body = {"model": "go/glm-5.2", "stream": True,
                    "messages": [{"role": "user", "content": "offline test"}],
                    "tools": [{"type": "function", "function": {"name": "probe", "description": "test", "parameters": {"type": "object", "properties": {"value": {"type": "string"}}}}}]}
            req = urllib.request.Request(f"http://127.0.0.1:{work}/v1/chat/completions",
                                         data=json.dumps(body).encode(), headers={
                                             "Authorization": "Bearer " + key,
                                             "Content-Type": "application/json", "User-Agent": "pi/offline-test",
                                             "session_id": "stable-conversation-id"})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=15) as response:
                data = response.read().decode()
            assert "probe" in data and "[DONE]" in data
            assert len(seen) == 1
            headers, forwarded = seen[0]
            lowered = {k.lower(): v for k, v in headers.items()}
            assert lowered["x-opencode-session"] == "stable-conversation-id"
            assert lowered["user-agent"] == "pi/offline-test"
            assert lowered["authorization"] == "Bearer synthetic-upstream-key"
            assert forwarded["model"] == "glm-5.2"
            assert forwarded["tools"][0]["function"]["name"] == "probe"
            print("PASS actual 8.0.23: Go prefix routing, per-conversation session and Pi user-agent forwarding, streaming tool traffic to a loopback mock")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        upstream.shutdown()
        upstream.server_close()


if __name__ == "__main__":
    main()
