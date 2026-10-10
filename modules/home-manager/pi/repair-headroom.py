"""Repair pi-headroom 0.1.0's undrained child pipes in the selected profile.

Run before Pi loads extensions, including after npm package refreshes. Only this
known upstream version is modified; source drift fails visibly rather than
silently applying a speculative patch. No other profile or running process is
changed.
"""

import json
import os
from pathlib import Path


OLD = """    // Unref streams so they don't keep the event loop alive on shutdown
    (proc.stdout as any)?.unref?.();
    (proc.stderr as any)?.unref?.();"""
NEW = """    // Drain both pipes: unref alone leaves proxy logging blocked on full buffers.
    // Discard output rather than accumulating potentially sensitive request logs.
    proc.stdout?.resume();
    proc.stderr?.resume();

""" + OLD


def repair(profile: Path) -> bool:
    package = profile / "npm/node_modules/pi-headroom"
    manifest = package / "package.json"
    if not manifest.exists():
        return False
    if json.loads(manifest.read_text()).get("version") != "0.1.0":
        return False
    manager = package / "src/proxy-manager.ts"
    source = manager.read_text()
    if NEW in source:
        return False
    if source.count(OLD) != 1:
        raise RuntimeError(f"Headroom pipe-drain repair target changed: {manager}")
    manager.write_text(source.replace(OLD, NEW, 1))
    return True


if __name__ == "__main__":
    repair(Path(os.environ.get("PI_CODING_AGENT_DIR", Path.home() / ".config/pi")))
