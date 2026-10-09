#!/usr/bin/env python3
"""Apply only the declared work-context denies/skill overrides, never auth/defaults."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile


CONTEXT_FLAGS = {"disableBundledSkills", "autoMemoryEnabled", "autoCompactEnabled", "channelsEnabled"}


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != {"permissions", "skillOverrides"} | CONTEXT_FLAGS:
        raise ValueError("Expected only context permissions, skills, and reviewed flags")
    if not all(isinstance(policy[key], bool) for key in CONTEXT_FLAGS):
        raise ValueError("Context flags must be booleans")
    permissions = policy["permissions"]
    if not isinstance(permissions, dict) or set(permissions) != {"deny"}:
        raise ValueError("Context policy must only deny tools")
    denies = permissions["deny"]
    if not isinstance(denies, list) or not all(
        isinstance(name, str) and re.fullmatch(r"[\w:@.*-]+", name) for name in denies
    ):
        raise ValueError("Expected tool-name denies only")
    skills = policy["skillOverrides"]
    if not isinstance(skills, dict) or not all(
        isinstance(name, str) and re.fullmatch(r"[\w:@./-]+", name) and mode == "off"
        for name, mode in skills.items()
    ):
        raise ValueError("Context policy can only disable named skills")


def merge(settings, policy):
    validate_policy(policy)
    if not isinstance(settings, dict):
        raise ValueError("Settings must be an object")
    # Deep copy: callers/tests retain the original; every unrelated field survives.
    result = json.loads(json.dumps(settings))
    permissions = result.setdefault("permissions", {})
    if not isinstance(permissions, dict):
        raise ValueError("Permissions must be an object")
    denies = permissions.setdefault("deny", [])
    if not isinstance(denies, list) or not all(isinstance(rule, str) for rule in denies):
        raise ValueError("Permission denies must be strings")
    for name in policy["permissions"]["deny"]:
        if name not in denies:
            denies.append(name)
    skills = result.setdefault("skillOverrides", {})
    if not isinstance(skills, dict):
        raise ValueError("Skill overrides must be an object")
    skills.update(policy["skillOverrides"])
    for key in CONTEXT_FLAGS:
        result[key] = policy[key]
    return result


def apply(home, policy):
    validate_policy(policy)
    path = home / ".config/claude-gmatter/settings.json"
    # Refuse to replace an unexpected declarative or cross-profile symlink.
    if path.is_symlink():
        raise ValueError("Work settings must be a writable regular file")
    current = json.loads(path.read_text()) if path.exists() else {}
    result = merge(current, policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="settings.json.context-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args()
    try:
        apply(Path.home(), json.loads(args.policy.read_text()))
    except (ValueError, OSError):
        # Settings/errors may contain credentials: never echo their contents.
        raise SystemExit("Work-context policy failed; settings left unchanged") from None


if __name__ == "__main__":
    main()
