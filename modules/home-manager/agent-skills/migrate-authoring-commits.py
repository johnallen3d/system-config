#!/usr/bin/env python3
"""Adopt only the reviewed personal Pi skill, retaining an exact backup."""

import argparse
import hashlib
from pathlib import Path


LEGACY_SHA256 = "3a339fd0badae9daf0501c7da6f1a8a0139200f994c6978fac8d6c315fee83d4"
SOURCE = Path(".config/pi/skills/authoring-commits/SKILL.md")
BACKUPS = Path(".local/state/system-config/skill-migrations/authoring-commits")


def migrate(home, dry_run=False):
    source = home / SOURCE
    # Existing managed links belong to Home Manager. Unknown links are left
    # untouched too; Home Manager's normal collision checks remain authoritative.
    if source.is_symlink() or not source.exists():
        return
    if not source.is_file() or source.resolve() != source:
        raise RuntimeError(f"Refusing indirect or non-file skill: {source}")
    original = source.read_bytes()
    if hashlib.sha256(original).hexdigest() != LEGACY_SHA256:
        raise RuntimeError(f"Refusing modified authoring-commits skill: {source}")
    backup = home / BACKUPS / LEGACY_SHA256 / "SKILL.md"
    # Validate existing backup paths before writing or removing anything.
    if backup.resolve() != backup:
        raise RuntimeError(f"Refusing symlinked skill backup: {backup}")
    if backup.exists() and (not backup.is_file() or backup.read_bytes() != original):
        raise RuntimeError(f"Refusing conflicting skill backup: {backup}")
    if dry_run:
        print(f"Would preserve reviewed skill at {backup} before Nix adoption")
        return
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        with backup.open("xb") as output:
            output.write(original)
        backup.chmod(source.stat().st_mode & 0o777)
    if backup.read_bytes() != original or source.is_symlink() or source.read_bytes() != original:
        raise RuntimeError("Skill or backup changed during migration; source retained")
    source.unlink()
    print(f"Preserved reviewed authoring-commits skill at {backup}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("home", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        migrate(args.home.resolve(), args.dry_run)
    except (OSError, RuntimeError) as error:
        parser.exit(1, f"authoring-commits migration: {error}\n")


if __name__ == "__main__":
    main()
