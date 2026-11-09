#!/usr/bin/env bash
# Adapted from Traces v0.6.45: retain the exact profile-local transcript path.
set -euo pipefail

input="$(cat)"
session_id="$(printf '%s' "$input" | jq -r '.session_id // empty')"
source_path="$(printf '%s' "$input" | jq -r '.transcript_path // empty')"

if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -n "$session_id" ]; then
  {
    printf 'export TRACES_CURRENT_TRACE_ID=%q\n' "$session_id"
    printf 'export TRACES_CURRENT_AGENT=%q\n' claude-code
    if [ -n "$source_path" ]; then
      printf 'export TRACES_CURRENT_SOURCE_PATH=%q\n' "$source_path"
    fi
  } >> "$CLAUDE_ENV_FILE"
fi
