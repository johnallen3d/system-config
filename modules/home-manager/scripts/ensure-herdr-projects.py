#!/usr/bin/env python3
"""Clone missing picker favorites; never mutate an existing destination."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def expand(value, home):
    return str(home / value[2:]) if value.startswith("~/") else value


def ensure(project, home, dry_run=False):
    relative = project["path"]
    if not relative.startswith("~/") or ".." in Path(relative[2:]).parts:
        raise ValueError(f"Favorite path must be home-relative: {relative}")
    destination = Path(expand(relative, home))
    if os.path.lexists(destination):
        # A parent repository is not enough: the favorite itself must be a root.
        result = subprocess.run(
            ["git", "-C", str(destination), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        if result.returncode or Path(result.stdout.strip()).resolve() != destination.resolve():
            raise ValueError(f"Refusing to overwrite non-repository destination: {destination}")
        print(f"Already present: {destination}", flush=True)
        return

    source = expand(project["clone_url"], home)
    if dry_run:
        print(f"Would clone {source} -> {destination}", flush=True)
        return

    print(f"Cloning {source} -> {destination}", flush=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Failed/interrupted clones must not leave a half-repository at the favorite
    # path, which a later activation might mistake for an existing checkout.
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-clone-", dir=destination.parent))
    try:
        subprocess.run(["git", "clone", "--", source, str(staging)], check=True)
        # Bundles are bootstrap seeds, not remotes to fetch/push against.
        if project["clone_url"].endswith(".bundle"):
            subprocess.run(["git", "-C", str(staging), "remote", "remove", "origin"], check=True)
        # Never replace a destination created by another process during cloning.
        if os.path.lexists(destination):
            raise ValueError(f"Destination appeared while cloning: {destination}")
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("home", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    errors = []
    seen = set()
    for project in json.loads(args.manifest.read_text()):
        if project["path"] in seen:
            continue
        seen.add(project["path"])
        try:
            ensure(project, args.home, args.dry_run)
        except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
            errors.append(f"{project['path']}: {error}")
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")


if __name__ == "__main__":
    main()
