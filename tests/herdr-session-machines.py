"""Check the patched Mac Herdr's catalog isolation using private test state.

Usage: python3 tests/herdr-session-machines.py [/path/to/herdr]
No SSH connections or changes to real profiles, clients, servers, or panes.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

binary = sys.argv[1] if len(sys.argv) > 1 else "herdr"

with tempfile.TemporaryDirectory(prefix="herdr-session-machines-") as temporary:
    root = Path(temporary)
    env = os.environ.copy()
    env.update(XDG_STATE_HOME=str(root / "state"), XDG_CONFIG_HOME=str(root / "config"))
    for key in ("HERDR_SESSION", "HERDR_SOCKET_PATH", "HERDR_CONFIG_PATH"):
        env.pop(key, None)

    def call(session, *args, inherited=False):
        context = env.copy()
        prefix = []
        if inherited:
            context["HERDR_SESSION"] = session
        else:
            prefix = ["--session", session]
        result = subprocess.run(
            [binary, *prefix, "machine", *args],
            env=context, capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(result.stdout) if args[0] == "list" else None

    def seed(session, identity, remote):
        directory = root / "state" / "herdr"
        if session != "default":
            directory /= Path("sessions") / session
        directory /= "client"
        directory.mkdir(parents=True)
        profile = dict(id=identity, label="Omarchy", target="johna@omarchy",
                       session=remote, enabled=True)
        (directory / "endpoints.json").write_text(json.dumps(dict(version=1, ssh=[profile])))
        (directory / "endpoint-selection.json").write_text(
            json.dumps(dict(version=1, selected_profile=identity)))
        return directory

    default = seed("default", "a" * 32, "default")
    personal = seed("personal", "b" * 32, "default")
    work = seed("work", "c" * 32, "work")
    original = (default / "endpoints.json").read_bytes()

    for session, identity, remote in (("default", "a", "default"),
                                      ("personal", "b", "default"),
                                      ("work", "c", "work")):
        for inherited in (False, True):
            rows = call(session, "list", "--json", inherited=inherited)
            assert len(rows) == 1, (session, rows)
            assert rows[0]["id"] == identity * 32, (session, rows)
            assert rows[0]["session"] == remote, (session, rows)
            assert rows[0]["selected"], (session, rows)
    assert call("empty", "list", "--json") == [], "New sessions must not inherit global profiles"

    # Machine changes stay within the selected local session, including CLI
    # calls from panes that inherit HERDR_SESSION instead of an explicit flag.
    call("work", "disable", "c" * 32, inherited=True)
    assert not call("work", "list", "--json")[0]["enabled"]
    assert call("personal", "list", "--json")[0]["enabled"]
    call("work", "rename", "c" * 32, "--label", "Work only")
    assert call("work", "list", "--json")[0]["label"] == "Work only"
    assert call("personal", "list", "--json")[0]["label"] == "Omarchy"
    call("work", "remove", "c" * 32)
    assert call("work", "list", "--json") == []
    assert len(call("personal", "list", "--json")) == 1
    assert (default / "endpoints.json").read_bytes() == original

print("PASS session-scoped catalogs, selection, inherited context, and isolated mutations")
