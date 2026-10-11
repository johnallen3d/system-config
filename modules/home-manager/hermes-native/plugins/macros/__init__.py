"""Direct, zero-model deterministic nutrition reports for Hermes."""

from __future__ import annotations

import asyncio
import os
import shlex
import signal
import tempfile
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
import re

COMMAND_DESCRIPTION = "Report read-only nutrition macros without using the agent."
COMMAND_ARGS_HINT = "[YYYY-MM-DD] [meal]"
USAGE = "Usage: /macros [YYYY-MM-DD] [meal]"
MACROS_TIMEOUT_SECONDS = 15.0
MISE = os.environ.get("HERMES_NATIVE_MISE", "")


class MacrosTimeoutError(RuntimeError):
    """Raised when a deterministic macros task exceeds its wall-clock budget."""


def _looks_like_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _parse_request(raw_args: str) -> tuple[tuple[str, ...], str] | str:
    """Map the slash-command grammar to a reviewed mise task and argv."""
    try:
        argv = shlex.split(raw_args, posix=True)
    except ValueError:
        return f"Invalid macros arguments; check the quotes.\n{USAGE}"

    if not argv:
        return ("macros",), "aggregate"

    if argv[0].startswith("-"):
        return f"Unsupported macros option: {argv[0]}.\n{USAGE}"

    if any(x.startswith("-") for x in argv):
        return f"Unsupported macros option.\n{USAGE}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", argv[0]) and not _looks_like_date(argv[0]):
        return f"Invalid macros date.\n{USAGE}"
    if _looks_like_date(argv[0]):
        if len(argv) == 1:
            return ("macros", "--", argv[0]), "aggregate"
        meal = " ".join(argv[1:]).strip()
        if not meal:
            return f"A meal is required after the date.\n{USAGE}"
        return ("macros-details", "--", "--date", argv[0], "--meal", meal), "itemized"

    meal = " ".join(argv).strip()
    if not meal:
        return USAGE
    return ("macros-details", "--", "--meal", meal), "itemized"


def _subprocess_environment(vault_dir: Path, isolated_home: Path) -> dict[str, str]:
    """Build a minimal environment with no gateway or model credentials."""
    return {
        "HOME": str(isolated_home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "MISE_AUTO_INSTALL": "0",
        "MISE_TRUSTED_CONFIG_PATHS": str(vault_dir),
        "PATH": os.environ.get("HERMES_NATIVE_TASK_PATH", ""),
        "UV_OFFLINE": "1",
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_NO_MANAGED_PYTHON": "1",
        "PYTHONNOUSERSITE": "1",
        "SSL_CERT_FILE": os.environ.get("SSL_CERT_FILE", ""),
        "TZ": os.environ.get("TZ", "America/New_York"),
        "TZDIR": os.environ.get("TZDIR", ""),
        "HERMES_NATIVE_OFFLINE": os.environ.get("HERMES_NATIVE_OFFLINE", "0"),
        "HERMES_NATIVE_STAGE": os.environ.get("HERMES_NATIVE_STAGE", "capabilities-offline"),
        "HERMES_NATIVE_READONLY": os.environ.get("HERMES_NATIVE_READONLY", "0"),
        "VAULT_DIR": str(vault_dir),
        "VAULT_NAME": os.environ.get("VAULT_NAME", "Personal"),
        "VLT_VAULT": os.environ.get("VLT_VAULT", os.environ.get("VAULT_NAME", "Personal")),
        "VLT_VAULT_PATH": str(vault_dir),
    }


async def _run_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout: float = MACROS_TIMEOUT_SECONDS,
) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        env=dict(env),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    communicate = asyncio.create_task(process.communicate())
    try:
        stdout, stderr = await asyncio.wait_for(
            asyncio.shield(communicate), timeout=timeout
        )
    except asyncio.TimeoutError as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await communicate
        raise MacrosTimeoutError from exc
    return process.returncode, stdout, stderr


async def _handle_macros(raw_args: str) -> str:
    request = _parse_request(raw_args)
    if isinstance(request, str):
        return request

    command, report_kind = request
    vault_dir = Path(os.environ.get("VAULT_DIR", "")).expanduser()
    if (os.environ.get("HERMES_NATIVE_OFFLINE") != "1"
            or not os.environ.get("VAULT_DIR")
            or not MISE.startswith("/nix/store/")
            or str(vault_dir) != os.environ.get("HERMES_HOME", "") + "/workspace/notes"
            or vault_dir.resolve() != vault_dir
            or not vault_dir.is_dir()):
        return "Macros are unavailable because the vault is not mounted."

    try:
        with tempfile.TemporaryDirectory(prefix="hermes-macros-") as home:
            returncode, stdout, stderr = await _run_process(
                (MISE, "run", *command),
                cwd=vault_dir,
                env=_subprocess_environment(vault_dir, Path(home)),
            )
    except MacrosTimeoutError:
        return f"Macros report timed out after {MACROS_TIMEOUT_SECONDS:g} seconds."
    except (OSError, RuntimeError):
        return "Macros report could not start. Try again or contact the Hermes operator."

    if returncode != 0:
        return f"Macros report failed (exit {returncode})."

    # The deterministic task owns formatting. Do not add markdown, labels, or an
    # agent-generated explanation around its stdout.
    return stdout.decode("utf-8", errors="replace")


def register(ctx) -> None:
    ctx.register_command(
        "macros",
        handler=_handle_macros,
        description=COMMAND_DESCRIPTION,
        args_hint=COMMAND_ARGS_HINT,
        argument_mode="text",
    )
