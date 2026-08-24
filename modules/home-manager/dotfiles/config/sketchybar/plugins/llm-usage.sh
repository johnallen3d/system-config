#!/usr/bin/env bash
set -u

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/llm-usage"
cache="$cache_dir/usage.json"
lock="$cache_dir/refresh.lock"
bin="@llmUsageBin@"
timeout_bin="@timeoutBin@"
stat_bin="@statBin@"
fish_bin="@fishBin@"

color_for_severity() {
  case "$1" in
    ok) printf '%s\n' '0xff9ccfd8' ;;
    warning|unknown) printf '%s\n' '0xfff6c177' ;;
    critical) printf '%s\n' '0xffeb6f92' ;;
    *) printf '%s\n' '0xfff6c177' ;;
  esac
}

compact_summary() {
  local value=$1
  value=${value//OpenCode Go/Go}
  value=${value//Claude Code/Claude}
  printf '%s\n' "${value// \(stale\)/}"
}

if [ "${1:-}" = "--test" ]; then
  [ "$(color_for_severity ok)" = "0xff9ccfd8" ] || exit 1
  [ "$(color_for_severity warning)" = "0xfff6c177" ] || exit 1
  [ "$(color_for_severity critical)" = "0xffeb6f92" ] || exit 1
  [ "$(color_for_severity unknown)" = "0xfff6c177" ] || exit 1
  [ "$(compact_summary 'Codex · OpenCode Go · Claude Code (stale)')" = "Codex · Go · Claude" ] || exit 1
  exit 0
fi

refresh() {
  mkdir -p "$cache_dir"
  if [ -d "$lock" ] && [ $(( $(date +%s) - $("$stat_bin" -c %Y "$lock") )) -gt 120 ]; then
    rmdir "$lock"
  fi
  mkdir "$lock" 2>/dev/null || return
  trap 'rmdir "$lock"' EXIT
  local tmp="$cache.$$"
  PI_CODING_AGENT_DIR="$HOME/.config/pi-work" "$timeout_bin" 30 "$fish_bin" -c 'exec "$argv[1]" json' -- "$bin" >"$tmp" && mv "$tmp" "$cache"
  rm -f "$tmp"
}

refresh &
[ -r "$cache" ] || exit 0

summary=$(compact_summary "$(jq -r '.presentation.summary' "$cache")")
severity=$(jq -r '.presentation.severity' "$cache")
color=$(color_for_severity "$severity")

if [ "${1:-}" = popup ]; then
  sketchybar --set llm_usage.codex drawing=off --set llm_usage.opencode_go drawing=off --set llm_usage.claude_code drawing=off
  jq -r '.presentation.providers[] | select(.visible) | [.provider, .label] | @tsv' "$cache" |
    while IFS=$'\t' read -r provider label; do
      case "$provider" in
        codex|opencode-go|claude-code) ;;
        *) continue ;;
      esac
      sketchybar --set "llm_usage.${provider//-/_}" drawing=on label="$label"
    done
  freshness=$(jq -r '.presentation.freshness' "$cache")
  sketchybar --set llm_usage.freshness label="$freshness"
  sketchybar --set llm_usage popup.drawing=toggle
  exit 0
fi

sketchybar --set llm_usage label="$summary" --set llm_usage_logo background.color="$color"
