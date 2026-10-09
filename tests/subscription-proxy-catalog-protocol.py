#!/usr/bin/env python3
"""Actual pinned gateway, three native Go protocols, synthetic streaming/tools.

Run on Omarchy with manager's PyYAML Python. All gateway/upstream state is
isolated in a temporary home; never sends requests to a real provider.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlparse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "modules/home-manager/subscription-proxy"))
import manager
import go_catalog


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    binary = shutil.which("cliproxyapi")
    assert binary
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            path = urlparse(self.path).path
            seen.append((path, {k.lower(): v for k, v in self.headers.items()}, body))
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            if path == "/v1/chat/completions":
                events = [
                    {"id": "mock", "object": "chat.completion.chunk", "model": body["model"], "choices": [{"index": 0, "delta": {"role": "assistant", "tool_calls": [{"index": 0, "id": "call_test", "type": "function", "function": {"name": "probe", "arguments": '{"value":"OK"}'}}]}, "finish_reason": None}]},
                    {"id": "mock", "object": "chat.completion.chunk", "model": body["model"], "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}]
            elif path == "/v1/responses":
                item = {"type": "function_call", "id": "fc_test", "call_id": "call_test", "name": "probe", "arguments": '{"value":"OK"}', "status": "completed"}
                events = [
                    {"type": "response.created", "response": {"id": "resp_test", "object": "response", "model": body["model"], "status": "in_progress", "output": []}},
                    {"type": "response.output_item.added", "output_index": 0, "item": dict(item, arguments="", status="in_progress")},
                    {"type": "response.function_call_arguments.delta", "item_id": "fc_test", "output_index": 0, "delta": item["arguments"]},
                    {"type": "response.output_item.done", "output_index": 0, "item": item},
                    {"type": "response.completed", "response": {"id": "resp_test", "object": "response", "model": body["model"], "status": "completed", "output": [item], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}}]
            elif path == "/v1/messages":
                events = [
                    {"type": "message_start", "message": {"id": "msg_test", "type": "message", "role": "assistant", "model": body["model"], "content": [], "stop_reason": None, "usage": {"input_tokens": 1, "output_tokens": 0}}},
                    {"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "call_test", "name": "probe", "input": {}}},
                    {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": '{"value":"OK"}'}},
                    {"type": "content_block_stop", "index": 0},
                    {"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None}, "usage": {"output_tokens": 1}},
                    {"type": "message_stop"}]
            else:
                raise AssertionError("Wrong native endpoint: " + path)
            for e in events:
                if "type" in e: self.wfile.write(("event: " + e["type"] + "\n").encode())
                self.wfile.write(("data: " + json.dumps(e) + "\n\n").encode())
            if path.endswith("chat/completions"): self.wfile.write(b"data: [DONE]\n\n")

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix="go-native-protocol-") as tmp, patch.dict(os.environ, HOME=tmp):
            old_root = manager.ROOT
            manager.ROOT = Path(tmp) / ".config/subscription-proxy"
            try:
                personal, work = port(), port()
                template = Path(tmp) / "template.json"
                manager.private_json(template, {"host": "127.0.0.1", "ports": {"personal": personal, "work": work}})
                manager.private_json(manager.ROOT / "endpoints.json", {"work": f"http://127.0.0.1:{work}", "personal": f"http://127.0.0.1:{personal}"})
                with contextlib.redirect_stdout(io.StringIO()): manager.seed_server(template)
                process = subprocess.Popen([binary, "--config", str(manager.ROOT / "server-work.yaml"), "--local-model"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                deadline = time.monotonic() + 15
                while True:
                    try: manager.request("work", "/config"); break
                    except ValueError:
                        assert time.monotonic() < deadline and process.poll() is None
                        time.sleep(0.2)
                keys = manager.go_providers()
                keys[0]["keys"] = [{"api-key": "synthetic-central-go-key"}]
                manager.request("work", "/config", "PATCH", {"api-keys": {"openai-compatibility": keys}})
                fixture = json.loads((ROOT / "tests/fixtures/subscription-go-sources.json").read_text())
                sources = [{"opencode-go": fixture["provider"]}, {"data": [{"id": i} for i in fixture["available"]]}]
                with patch.object(manager, "public_json", side_effect=sources), contextlib.redirect_stdout(io.StringIO()):
                    manager.refresh_go("/bin/synthetic-helper", server=True)
                assert len(manager.cached_go_models()) == 34
                assert not seen, "Catalog refresh must never call inference"
                first = manager.request("work", "/config")["api-keys"]
                with contextlib.redirect_stdout(io.StringIO()): manager.refresh_go("/bin/synthetic-helper", server=True, cached=True)
                assert manager.request("work", "/config")["api-keys"] == first, "Repeated reconciliation must be idempotent"
                print("PASS actual 8.0.23 catalog reconciliation, native-group registration, idempotence and zero inference during refresh")
                native = manager.request("work", "/config")["api-keys"]
                native["openai-compatibility"][0]["base-url"] = f"http://127.0.0.1:{upstream.server_port}/v1"
                native["xai"][0]["base-url"] = f"http://127.0.0.1:{upstream.server_port}/v1"
                native["claude"][0]["base-url"] = f"http://127.0.0.1:{upstream.server_port}"
                manager.request("work", "/config", "PATCH", {"api-keys": native})
                token = manager.credentials()["work"]["client"]
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for model, expected in (("glm-5.2", "/v1/chat/completions"), ("gpt-6-luna", "/v1/responses"), ("qwen3.8-max", "/v1/messages")):
                    body = {"model": "go/" + model, "stream": True, "max_tokens": 32,
                            "messages": [{"role": "user", "content": "synthetic test"}],
                            "tools": [{"type": "function", "function": {"name": "probe", "description": "test", "parameters": {"type": "object", "properties": {"value": {"type": "string"}}}}}]}
                    req = urllib.request.Request(f"http://127.0.0.1:{work}/v1/chat/completions", data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "User-Agent": "pi/synthetic-test", "session_id": "stable-go-protocol-session"})
                    with opener.open(req, timeout=20) as r: response = r.read().decode()
                    assert "probe" in response and "[DONE]" in response, expected
                    path, headers, forwarded = seen[-1]
                    assert path == expected, (model, path)
                    assert forwarded["model"] == model
                    assert headers["user-agent"] == "pi/synthetic-test"
                    assert headers["x-opencode-session"] == "stable-go-protocol-session"
                    assert headers.get("authorization", "").removeprefix("Bearer ") == "synthetic-central-go-key"
                    if expected.endswith("messages"):
                        assert headers.get("x-api-key") == "synthetic-central-go-key", "Go Messages requires explicit per-key x-api-key"
                    print(f"PASS actual Go {expected} native routing, tool streaming and stable Pi session/User-Agent headers")
            finally:
                manager.ROOT = old_root
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        upstream.shutdown(); upstream.server_close()


if __name__ == "__main__": main()
