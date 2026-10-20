#!/usr/bin/env python3
"""Profile-local npm policy and final security reporting for harness refresh."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

PROFILES = {"personal": "pi", "work": "pi-work", "notes": "pi-notes"}

# Reviewed, exact-version decisions for generated profile npm manifests only.
# esbuild selects/validates its platform binary (including hash-checked fallback
# downloads). fsevents 2.3.3 ships fsevents.node and no install lifecycle script;
# its old lock metadata nevertheless advertises one. No build is needed.
# Git packages must carry their own policy in their source repository instead.
PROFILE_SCRIPT_POLICY = {"esbuild@0.28.2": True, "fsevents@2.3.3": False}


def apply_profile_policy(root):
    manifest = root / "package.json"
    lock = root / "package-lock.json"
    if not manifest.exists() or not lock.exists():
        return
    data = json.loads(manifest.read_text())
    packages = json.loads(lock.read_text()).get("packages", {})
    decisions = {}
    for spec, allowed in PROFILE_SCRIPT_POLICY.items():
        name, version = spec.rsplit("@", 1)
        for path, metadata in packages.items():
            if (path.rsplit("node_modules/", 1)[-1] == name
                    and metadata.get("version") == version
                    and metadata.get("resolved", "").startswith("https://registry.npmjs.org/")):
                decisions[spec] = allowed
                break
    if not decisions:
        return
    before = json.dumps(data, sort_keys=True)
    policy = data.setdefault("allowScripts", {})
    applied = []
    for spec, allowed in decisions.items():
        # Honor exact, name-only, and exact-version-disjunction user decisions.
        name, version = spec.rsplit("@", 1)
        covered = any(key in (name, name + "@*") or
                      key.startswith(name + "@") and version in
                      (part.strip() for part in key[len(name) + 1:].split("||"))
                      for key in policy)
        if not covered:
            policy[spec] = allowed
            applied.append(spec)
    if json.dumps(data, sort_keys=True) != before:
        with tempfile.NamedTemporaryFile(mode="w", dir=root, delete=False) as output:
            temporary = Path(output.name)
            try:
                output.write(json.dumps(data, indent=2) + "\n")
                output.close()
                temporary.replace(manifest)
            finally:
                temporary.unlink(missing_ok=True)
        print("Recorded reviewed profile install-script decisions: " + ", ".join(sorted(applied)))


def npm_json(args, root, profile, destination):
    env = dict(os.environ, PI_CODING_AGENT_DIR=str(profile), npm_config_audit="true")
    try:
        result = subprocess.run(["npm", *args], cwd=root, env=env,
                                capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"npm {' '.join(args)}: {exc}") from exc
    destination.write_text(result.stdout)
    destination.with_suffix(".stderr.log").write_text(result.stderr)
    try:
        data = json.loads(result.stdout)
    except ValueError as exc:
        raise RuntimeError(f"npm returned no valid JSON; see {destination}") from exc
    if data.get("error") or result.returncode not in (0, 1):
        raise RuntimeError(f"npm report failed; see {destination}")
    return result.returncode, data


def report(log_dir):
    summary = {"profiles": {}, "security_findings": False, "report_errors": False}
    for label, directory in PROFILES.items():
        profile = Path.home() / ".config" / directory
        failed = (log_dir / f"{label}.failed").exists()
        entry = {"refresh": "failed" if failed else "succeeded", "roots": []}
        summary["profiles"][label] = entry
        print(f"[{label}] {'FAILED' if failed else 'Refreshed'}; log: {log_dir / (label + '.log')}")
        # Preserve unusual warnings too, not just the ones we anticipated.
        log = (log_dir / f"{label}.log").read_text(errors="replace")
        warnings = set()
        for line in log.splitlines():
            match = re.search(r"npm warn\s*(.*)", line)
            if not match:
                continue
            warning = match.group(1)
            if warning.startswith("deprecated "):
                continue  # Report deprecations from the final lock below.
            if warning.startswith("install-scripts"):
                detail = warning.removeprefix("install-scripts").strip()
                if not detail or any(text in detail for text in (
                        "not yet covered by allowScripts", "(postinstall:",
                        "(preinstall:", "(install:", "(prepare:", "Run `npm install-scripts")):
                    continue  # The final inventory replaces only this chatter.
            if warning:
                warnings.add(warning)
        for warning in sorted(warnings):
            print(f"[{label}] WARNING: {warning}")
        if failed:
            print(f"[{label}] Security checks skipped: dependency reconciliation failed.")
            continue
        roots_file = log_dir / f"{label}.roots"
        roots = dict.fromkeys(roots_file.read_text().splitlines()) if roots_file.exists() else {}
        for index, path in enumerate(roots):
            root = Path(path)
            name = str(root.relative_to(profile))
            record = {"root": name}
            entry["roots"].append(record)
            try:
                code, audit = npm_json(["audit", "--json", "--omit=dev", "--legacy-peer-deps"],
                                       root, profile, log_dir / f"{label}-{index}.audit.json")
                counts = audit.get("metadata", {}).get("vulnerabilities")
                if not isinstance(counts, dict) or "total" not in counts or (code and not counts["total"]):
                    raise RuntimeError("incomplete audit result")
                record["vulnerabilities"] = counts
                total = counts["total"]
                if total:
                    summary["security_findings"] = True
                    levels = ", ".join(f"{counts[level]} {level}" for level in
                                       ("critical", "high", "moderate", "low", "info") if counts.get(level))
                    print(f"[{label}] {name}: SECURITY WARNING: {levels} ({total} affected packages)")
                    upgrades = set()
                    for item in audit.get("vulnerabilities", {}).values():
                        fix = item.get("fixAvailable")
                        if isinstance(fix, dict) and fix.get("isSemVerMajor"):
                            upgrades.add(f"{fix['name']}@{fix['version']}")
                    if upgrades:
                        print(f"[{label}] {name}: source-level major upgrade required: {', '.join(sorted(upgrades))}")
                else:
                    print(f"[{label}] {name}: audit clean")
                code, scripts = npm_json(["install-scripts", "ls", "--json"], root, profile,
                                         log_dir / f"{label}-{index}.scripts.json")
                if code or not isinstance(scripts.get("allowScripts"), list):
                    raise RuntimeError("incomplete install-script policy report")
                pending = sorted({change["key"] for package in scripts["allowScripts"]
                                  for change in package.get("changes", [])
                                  if change.get("change") == "pending"})
                record["unreviewed_scripts"] = pending
                if pending:
                    print(f"[{label}] {name}: unreviewed install scripts: {', '.join(pending)}")
                packages = json.loads((root / "package-lock.json").read_text()).get("packages", {})
                deprecated = sorted({f"{path.rsplit('node_modules/', 1)[-1]}@{metadata.get('version', '?')}"
                                     for path, metadata in packages.items()
                                     if metadata.get("deprecated") and not metadata.get("dev")})
                record["deprecated"] = deprecated
                if deprecated:
                    print(f"[{label}] {name}: deprecated dependencies: {', '.join(deprecated)}")
            except (RuntimeError, OSError, ValueError, KeyError, TypeError) as exc:
                summary["report_errors"] = True
                record["error"] = str(exc)
                print(f"[{label}] {name}: SECURITY CHECK FAILED: {exc}", file=sys.stderr)
    (log_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return int(summary["report_errors"])


if __name__ == "__main__":
    operation, path = sys.argv[1:]
    if operation == "policy":
        apply_profile_policy(Path(path))
    elif operation == "report":
        raise SystemExit(report(Path(path)))
    else:
        raise SystemExit(f"Unknown operation: {operation}")
