#!/usr/bin/env python3
"""Check the pi-01-only LAN forwarder, authentication guard, and optional runtime."""

import argparse
import importlib.util
import json
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAN = "192.168.4.26:8384"
SOURCE = "192.168.5.11/32"
# Import the guard without creating artifacts alongside managed source files.
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "auth_guard", ROOT / "modules/home-manager/omarchy-syncthing/check-auth.py"
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def check_source():
    expression = """
      let flake = builtins.getFlake @ROOT@;
          home = flake.homeConfigurations."johna@omarchy".config;
          mac = flake.darwinConfigurations.m4-mbp.config.home-manager.users."john.allen";
      in {
        unit = home.systemd.user.services.syncthing-lan;
        macLan = builtins.hasAttr "syncthing-lan" mac.systemd.user.services;
      }
    """.replace("@ROOT@", json.dumps(str(ROOT)))
    config = json.loads(run(
        "nix", "--extra-experimental-features", "nix-command flakes",
        "eval", "--impure", "--json", "--expr", expression,
    ))
    assert not config["macLan"]
    unit = config["unit"]
    service = unit["Service"]
    command = " ".join(service["ExecStart"])
    expected = f"TCP4-LISTEN:8384,bind=192.168.4.26,reuseaddr,fork,range={SOURCE} TCP4:127.0.0.1:8384"
    assert command.endswith(expected), command
    assert "python3 -I" in " ".join(service["ExecStartPre"])
    assert "check-auth.py" in " ".join(service["ExecStartPre"])
    assert service["Restart"] == "always" and service["RestartSec"] == 10
    assert service["NoNewPrivileges"]
    assert service["ProtectSystem"] == "strict"
    assert service["ProtectHome"] == "read-only"
    assert service["RestrictAddressFamilies"] == ["AF_INET", "AF_UNIX"]
    assert "syncthing.service" in unit["Unit"]["After"]
    assert unit["Install"]["WantedBy"] == ["default.target"]
    print("PASS source: Omarchy-only, exact LAN bind, pi-01-only source, auth guard")


def expect_failure(callback):
    try:
        callback()
    except RuntimeError:
        return
    raise AssertionError("Expected fail-closed authentication guard")


def check_guard():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "config.xml"
        for gui in ("", "<gui/>", "<gui><user>test</user></gui>",
                    "<gui><password>test</password></gui>",
                    ("<gui><user>test</user><password>test</password>"
                     "<insecureAdminAccess>true</insecureAdminAccess></gui>")):
            path.write_text(f"<configuration>{gui}</configuration>")
            expect_failure(lambda: guard.validate_config(path))
        path.write_text("<configuration><gui><user>test</user><password>test</password>"
                        "</gui></configuration>")
        guard.validate_config(path)

    class AuthResponse(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.recv(4096)
            self.request.sendall(
                f"HTTP/1.1 {self.server.code} Test\r\nContent-Length: 0\r\n\r\n".encode()
            )

    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), AuthResponse) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}/rest/config"
        try:
            for code in (401, 403):
                server.code = code
                guard.require_auth(url)
            for code in (200, 500):
                server.code = code
                expect_failure(lambda: guard.require_auth(url))
        finally:
            server.shutdown()
    print("PASS guard: missing/disabled credentials and unprotected REST fail closed")


def check_forwarding():
    if sys.platform != "linux":
        print("SKIP socat fixture: run on Linux for the alternate-loopback source check")
        return
    socat = shutil.which("socat")
    assert socat, "socat must be available for the Linux source-filter regression"

    class Echo(socketserver.BaseRequestHandler):
        def handle(self):
            data = self.request.recv(4096)
            if data:
                self.request.sendall(b"forwarded:" + data)

    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), Echo) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with socket.socket() as temporary:
            temporary.bind(("127.0.0.1", 0))
            port = temporary.getsockname()[1]
        process = subprocess.Popen([
            socat, f"TCP4-LISTEN:{port},bind=127.0.0.1,reuseaddr,fork,range=127.0.0.1/32",
            f"TCP4:127.0.0.1:{server.server_address[1]}",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                assert process.poll() is None, "socat exited before fixture was ready"
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1) as client:
                        client.sendall(b"probe")
                        assert client.recv(128) == b"forwarded:probe"
                    break
                except ConnectionRefusedError:
                    time.sleep(0.05)
            else:
                raise AssertionError("socat fixture did not start")
            with socket.socket() as client:
                client.settimeout(2)
                client.bind(("127.0.0.2", 0))
                client.connect(("127.0.0.1", port))
                try:
                    client.sendall(b"denied")
                    assert client.recv(128) == b"", "Disallowed source reached backend"
                except ConnectionResetError:
                    pass
        finally:
            process.terminate()
            process.wait(timeout=5)
            server.shutdown()
    print("PASS socat fixture: allowed source forwards; other source is rejected")


def check_installed():
    assert run("systemctl", "--user", "is-active", "syncthing-lan.service") == "active"
    assert run("systemctl", "--user", "is-enabled", "syncthing-lan.service") == "enabled"
    command = run("systemctl", "--user", "show", "syncthing-lan", "-p", "ExecStart", "--value")
    assert f"range={SOURCE}" in command and "bind=192.168.4.26" in command
    listeners = run("ss", "-ltnpH", "sport = :8384").splitlines()
    forwarders = [line for line in listeners if '"socat"' in line]
    assert forwarders and all(line.split()[3] == LAN for line in forwarders), forwarders
    guard.main()
    reply_route = run("ip", "-4", "route", "get", "192.168.5.11", "from", "192.168.4.26")
    assert "dev enp3s0" in reply_route and "tailscale0" not in reply_route, reply_route
    saved_rule = run(
        "nmcli", "-g", "ipv4.routing-rules", "connection", "show",
        "f8ff9eb7-0d58-3b21-bc76-6649a6005a4b",
    )
    assert "priority 2500" in saved_rule and "192.168.5.11" in saved_rule
    assert "table 254" in saved_rule, saved_rule
    # Omarchy itself is not an allowed LAN source. Only localhost/tailnet remain
    # usable locally; verify the forwarder's filter even without firewall access.
    with socket.create_connection(("192.168.4.26", 8384), timeout=5) as client:
        try:
            client.sendall(b"GET /rest/noauth/health HTTP/1.0\r\n\r\n")
            assert client.recv(128) == b"", "Omarchy's LAN source must be rejected"
        except ConnectionResetError:
            pass
    print("PASS installed: exact LAN socket, source filter, authentication, persistent LAN reply route")


def check_lan_client():
    # Run this mode on pi-01; no Nix evaluation, credentials, or source changes.
    opener = guard.build_opener(guard.ProxyHandler({}))
    with opener.open(f"http://{LAN}/rest/noauth/health", timeout=10) as response:
        assert json.load(response)["status"] == "OK"
    guard.require_auth(f"http://{LAN}/rest/config")
    print("PASS LAN client: Syncthing health reachable; unauthenticated config rejected")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--lan-client", action="store_true")
    args = parser.parse_args()
    if args.lan_client:
        check_lan_client()
        return
    check_source()
    check_guard()
    check_forwarding()
    if args.installed:
        check_installed()


if __name__ == "__main__":
    main()
