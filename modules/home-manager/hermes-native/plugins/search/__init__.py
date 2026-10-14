"""Direct, zero-model deterministic search commands for Hermes."""

from __future__ import annotations

import asyncio
import os
import shlex
import signal
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

COMMAND_DESCRIPTION = "Search deterministic read-only data without using the agent."
COMMAND_ARGS_HINT = "[domain] [--nutrition] [query]"
USAGE = "Usage: /search food [--nutrition] <query>"
SEARCH_TIMEOUT_SECONDS = 10.0
TELEGRAM_OUTPUT_LIMIT = 3_800
MISE = os.environ.get("HERMES_NATIVE_MISE", "")

# Keep command construction explicit. Adding a domain requires a reviewed route here;
# user input can never select a mise task or task subcommand.
DOMAIN_ROUTES = {
    "food": (MISE, "run", "common-food", "--", "search"),
}


class SearchTimeoutError(RuntimeError):
    """Raised when a deterministic search exceeds its wall-clock budget."""


def _parse_request(raw_args: str) -> tuple[str, str, bool] | str:
    try:
        argv = shlex.split(raw_args, posix=True)
    except ValueError:
        return f"Invalid search arguments; check the quotes.\n{USAGE}"

    if not argv:
        return USAGE

    domain = argv[0].lower()
    if domain not in DOMAIN_ROUTES:
        return f"Unsupported search domain. Supported domains: {', '.join(DOMAIN_ROUTES)}.\n{USAGE}"

    nutrition = False
    query_parts: list[str] = []
    for argument in argv[1:]:
        if argument in {"--nutrition", "-n"}:
            if nutrition:
                return f"The --nutrition option can only be supplied once.\n{USAGE}"
            nutrition = True
        elif argument.startswith("-"):
            return f"Unsupported search option: {argument}.\n{USAGE}"
        else:
            query_parts.append(argument)

    query = " ".join(query_parts).strip()
    if not query:
        return USAGE
    if len(query) > 512:
        return f"Search query is too long (maximum 512 characters).\n{USAGE}"

    return domain, query, nutrition


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
        "VAULT_DIR": str(vault_dir),
        "VLT_VAULT_PATH": str(vault_dir),
        "VLT_VAULT": "Personal",
    }


async def _run_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout: float = SEARCH_TIMEOUT_SECONDS,
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
        raise SearchTimeoutError from exc
    return process.returncode, stdout, stderr


def _format_output(stdout: bytes) -> str:
    output = stdout.decode("utf-8", errors="replace").strip()
    if not output:
        return "Search completed with no results."

    # Telegram's normal proportional font makes `column` output look jagged. A
    # fenced block preserves the task's aligned table and allows wide nutrition
    # results to scroll horizontally instead of wrapping columns together.
    prefix = "```\n"
    closing = "\n```"
    if len(prefix) + len(output) + len(closing) <= TELEGRAM_OUTPUT_LIMIT:
        return f"{prefix}{output}{closing}"

    suffix = "\n… Results truncated. Refine the query for a shorter list."
    budget = TELEGRAM_OUTPUT_LIMIT - len(prefix) - len(closing) - len(suffix)
    kept_lines: list[str] = []
    used = 0
    for line in output.splitlines():
        added = len(line) + (1 if kept_lines else 0)
        if used + added > budget:
            break
        kept_lines.append(line)
        used += added
    truncated = "\n".join(kept_lines)
    return f"{prefix}{truncated}{closing}{suffix}"


async def _handle_search(raw_args: str) -> str:
    request = _parse_request(raw_args)
    if isinstance(request, str):
        return request

    domain, query, nutrition = request
    vault_dir = Path(os.environ.get("VAULT_DIR", "")).expanduser()
    if not os.environ.get("VAULT_DIR") or not vault_dir.is_dir():
        return "Search is unavailable because the vault is not mounted."

    command = (*DOMAIN_ROUTES[domain], query)
    if nutrition:
        command = (*command, "--nutrition")
    try:
        with tempfile.TemporaryDirectory(prefix="hermes-search-") as home:
            returncode, stdout, _stderr = await _run_process(
                command,
                cwd=vault_dir,
                env=_subprocess_environment(vault_dir, Path(home)),
            )
    except SearchTimeoutError:
        return f"Food search timed out after {SEARCH_TIMEOUT_SECONDS:g} seconds. Try a narrower query."
    except (OSError, RuntimeError):
        return "Food search could not start. Try again or contact the Hermes operator."

    if returncode != 0:
        return f"Food search failed (exit {returncode}). Check the query and try again."
    return _format_output(stdout)


def _install_commands_listing_compatibility() -> None:
    """Include plugin commands in /commands on the pinned Hermes release."""
    from hermes_cli import slash_exec

    current = slash_exec._skill_commands
    if getattr(current, "_pi_cielo_search_listing", False):
        return

    def listed_commands() -> dict:
        entries = dict(current())
        try:
            from hermes_cli.plugins import get_plugin_commands

            enabled = "search" in get_plugin_commands()
        except Exception:  # noqa: BLE001 - listing compatibility must never break dispatch
            enabled = False
        if enabled:
            entries.setdefault(
                "/search",
                {"description": f"{COMMAND_DESCRIPTION} {COMMAND_ARGS_HINT}"},
            )
        return entries

    listed_commands._pi_cielo_search_listing = True
    slash_exec._skill_commands = listed_commands


def register(ctx) -> None:
    ctx.register_command(
        "search",
        handler=_handle_search,
        description=COMMAND_DESCRIPTION,
        args_hint=COMMAND_ARGS_HINT,
        argument_mode="text",
    )
    _install_commands_listing_compatibility()
