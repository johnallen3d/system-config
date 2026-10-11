#!/usr/bin/env python3
"""Create a constrained Hermes skill proposal in the synced Personal vault."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import NoReturn

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
MAX_FILES = 20
MAX_FILE_BYTES = 256 * 1024
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(
        rb"(?i)(?:password|passwd|api[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*['\"]?[^\s'\"]{8,}"
    ),
    re.compile(rb"\b(?:gh[opsu]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b"),
)


def fail(message: str) -> NoReturn:
    raise SystemExit(f"handoff proposal: {message}")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_relative_file(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        fail(f"invalid skill path: {value}")
    if path.parts[0] != "skills" or len(path.parts) < 4:
        fail(f"skill path must be below skills/<group>/<skill>/<file>: {value}")
    if path.as_posix() != value or any(part in {"", "."} for part in path.parts):
        fail(f"invalid skill path: {value}")
    return path


def safe_regular_file(root: Path, relative: PurePosixPath) -> Path:
    candidate = root.joinpath(*relative.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError):
        fail(f"source is missing or escapes its root: {relative}")
    if any(p.is_symlink() for p in [candidate, *candidate.parents]) or not candidate.is_file() or candidate.stat().st_nlink != 1:
        fail(f"source must be a regular non-symlink file: {relative}")
    return candidate


def scan_secrets(label: str, data: bytes) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(data):
            fail(f"possible secret detected in {label}; proposal was not created")


def fsync_tree(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            with path.open("rb") as source:
                os.fsync(source.fileno())
    for path in sorted(
        (item for item in root.rglob("*") if item.is_dir()), reverse=True
    ):
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    descriptor = os.open(root, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package runtime Hermes skill changes for human-reviewed system-config promotion."
    )
    parser.add_argument("--id", required=True, help="lowercase proposal identifier")
    parser.add_argument("--title", required=True)
    rationale = parser.add_mutually_exclusive_group(required=True)
    rationale.add_argument("--rationale")
    rationale.add_argument("--rationale-file", type=Path)
    parser.add_argument(
        "--test",
        action="append",
        required=True,
        dest="tests",
        help="expected validation command or manual check (repeatable)",
    )
    parser.add_argument(
        "--file",
        action="append",
        required=True,
        dest="files",
        help="runtime path below skills/, for example skills/health/macros/SKILL.md",
    )
    parser.add_argument(
        "--handoff-root",
        type=Path,
        help="override the default VAULT_DIR/tools/hermes-handoff (tests only)",
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=Path(os.environ.get("HERMES_HOME", "/nonexistent")),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--bundled-root",
        type=Path,
        default=Path(os.environ.get("HERMES_NATIVE_ASSETS", "/nonexistent")),
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if os.environ.get("HERMES_NATIVE_OFFLINE") != "1":
        fail("native proposal creation is gated to isolated disposable validation")
    if not ID_PATTERN.fullmatch(args.id):
        fail("id must contain 3-64 lowercase letters, digits, or hyphens")
    if len(args.title.strip()) < 8 or len(args.title) > 160:
        fail("title must contain 8-160 characters")
    if not args.files or len(args.files) > MAX_FILES:
        fail(f"a proposal must contain 1-{MAX_FILES} files")

    if args.rationale_file:
        rationale_text = args.rationale_file.read_text(encoding="utf-8")
    else:
        rationale_text = args.rationale
    assert rationale_text is not None
    rationale_text = rationale_text.strip()
    if len(rationale_text) < 20:
        fail("rationale must contain at least 20 characters")
    tests = [test.strip() for test in args.tests if test.strip()]
    if not tests:
        fail("at least one non-empty test is required")

    vault_dir = os.environ.get("VLT_VAULT_PATH") or os.environ.get("VAULT_DIR")
    if args.handoff_root:
        handoff_root = args.handoff_root
    elif vault_dir:
        vault_root = Path(vault_dir)
        if not vault_root.is_dir():
            fail(f"configured Personal vault does not exist: {vault_root}")
        handoff_root = vault_root / "tools" / "hermes-handoff"
    else:
        fail(
            "VLT_VAULT_PATH or VAULT_DIR is required unless --handoff-root is supplied"
        )

    for root in [args.runtime_root, args.bundled_root, handoff_root]:
        for part in [*root.parents, root]:
            if part.is_symlink():
                fail("symlink root refused")
    for path in [handoff_root / "proposals", handoff_root / ".staging", handoff_root / ".gitignore", handoff_root / ".handoff.lock"]:
        if path.is_symlink() or (path.is_file() and path.stat().st_nlink != 1):
            fail("linked handoff entry refused")
    runtime_root = args.runtime_root.resolve()
    bundled_root = args.bundled_root.resolve()
    proposals_root = handoff_root / "proposals"
    staging_root = handoff_root / ".staging"
    proposals_root.mkdir(parents=True, exist_ok=True, mode=0o755)
    staging_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    ignore_path = handoff_root / ".gitignore"
    expected_ignore = b"/.handoff.lock\n/.staging/\n"
    if ignore_path.exists() and ignore_path.read_bytes() != expected_ignore:
        fail(f"refusing to replace unexpected handoff ignore rules: {ignore_path}")
    if not ignore_path.exists():
        descriptor, temporary = tempfile.mkstemp(prefix=".gitignore.", dir=handoff_root)
        try:
            with os.fdopen(descriptor, "wb") as ignore_file:
                ignore_file.write(expected_ignore)
                ignore_file.flush()
                os.fsync(ignore_file.fileno())
            os.chmod(temporary, 0o644)
            os.replace(temporary, ignore_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    text_to_scan = "\n".join([args.title, rationale_text, *tests]).encode()
    if len(text_to_scan) > MAX_FILE_BYTES:
        fail("proposal metadata too large")
    scan_secrets("proposal metadata", text_to_scan)

    records: list[dict[str, object]] = []
    seen: set[str] = set()
    payloads: list[tuple[PurePosixPath, bytes, int]] = []
    for value in args.files:
        relative = validate_relative_file(value)
        relative_text = relative.as_posix()
        if relative_text in seen:
            fail(f"duplicate file: {relative_text}")
        seen.add(relative_text)

        runtime_file = safe_regular_file(runtime_root, relative)
        proposed = runtime_file.read_bytes()
        if not proposed or len(proposed) > MAX_FILE_BYTES:
            fail(f"file must contain 1-{MAX_FILE_BYTES} bytes: {relative_text}")
        try:
            proposed.decode("utf-8")
        except UnicodeDecodeError:
            fail(f"skill payload must be UTF-8 text: {relative_text}")
        scan_secrets(relative_text, proposed)

        bundled_file = bundled_root.joinpath(*relative.parts)
        base_sha256: str | None
        if bundled_file.exists():
            base_file = safe_regular_file(bundled_root, relative)
            base = base_file.read_bytes()
            base_sha256 = digest(base)
            if proposed == base:
                fail(f"file is unchanged from the bundled baseline: {relative_text}")
        else:
            base_sha256 = None

        source_mode = stat.S_IMODE(runtime_file.stat().st_mode)
        mode = 0o755 if source_mode & 0o111 else 0o644
        target = PurePosixPath("modules/home-manager/hermes-native") / relative
        records.append(
            {
                "source": relative_text,
                "target": target.as_posix(),
                "base_sha256": base_sha256,
                "proposed_sha256": digest(proposed),
                "mode": format(mode, "04o"),
            }
        )
        payloads.append((target, proposed, mode))

    final_dir = proposals_root / args.id
    lock_path = handoff_root / ".handoff.lock"
    lock_path.touch(mode=0o600, exist_ok=True)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if final_dir.exists():
            fail(f"proposal already exists: {args.id}")

        stage = Path(tempfile.mkdtemp(prefix=f".{args.id}.", dir=staging_root))
        stage.chmod(0o755)
        try:
            files_root = stage / "files"
            files_root.mkdir(mode=0o755)
            for target, proposed, mode in payloads:
                destination = files_root.joinpath(*target.parts)
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                destination.write_bytes(proposed)
                destination.chmod(mode)

            manifest = {
                "schema_version": 2,
                "owner": "system-config",
                "id": args.id,
                "title": args.title.strip(),
                "status": "proposed",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "hermes-runtime",
                "files": records,
            }
            (stage / "manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            (stage / "rationale.md").write_text(rationale_text + "\n", encoding="utf-8")
            (stage / "tests.md").write_text(
                "# Proposed validation\n\n"
                + "\n".join(f"- `{test}`" for test in tests)
                + "\n",
                encoding="utf-8",
            )
            fsync_tree(stage)
            os.replace(stage, final_dir)
            descriptor = os.open(proposals_root, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)

    print(f"Created Hermes handoff proposal {args.id}")
    print("Status: proposed; awaiting Syncthing, Git commit, and human review")
    print(f"Path: {final_dir}")


if __name__ == "__main__":
    main()
