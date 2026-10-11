#!/usr/bin/env bash
# No-agent child contract. No production execution or transport at the #758 gate.
set -euo pipefail
if [[ "${HERMES_NATIVE_OFFLINE:-}" != "1" || "${VAULT_DIR:-}" != "${HERMES_HOME:?}/workspace/notes" ]]; then
    printf '%s\n' 'Morning brief is INACTIVE outside an isolated disposable capability check.' >&2
    exit 64
fi
[[ "$(realpath "$VAULT_DIR")" == "$VAULT_DIR" ]] || exit 64
cd "$VAULT_DIR"
# Hermes (later sole owner) delivers stdout; the task never receives a bot token.
export MORNING_BRIEF_DELIVERY=stdout
exec "${HERMES_NATIVE_MISE:?}" run morning-brief
