#!/usr/bin/env bash
set -u

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/llm-usage"
cache="$cache_dir/usage.json"
lock="$cache_dir/refresh.lock"
bin="@llmUsageBin@"

refresh() {
  mkdir -p "$cache_dir"
  mkdir "$lock" 2>/dev/null || return
  trap 'rmdir "$lock"' EXIT
  local tmp="$cache.$$"
  "$bin" json >"$tmp" && mv "$tmp" "$cache"
  rm -f "$tmp"
}

[ -e "$lock" ] || refresh &
[ -r "$cache" ] || exit 0

summary=$(jq -r '
  def name: {"codex":"Codex", "opencode-go":"Go", "claude-code":"Claude"}[.] // .;
  .providers | map(
    select(.status != "unavailable") |
    . as $p |
    [$p.windows[] | select(.used_percent != null) | "\(.used_percent | round)% \(.label)"] as $windows |
    "\($p.provider | name) \($windows | join(" "))"
  ) | join(" · ")
' "$cache")

color=$(jq -r '
  [.providers[] | .status, (.windows[]?.status)] as $states |
  if ($states | index("rate_limited")) then "0xffeb6f92"
  elif ($states | index("unavailable")) then "0xfff6c177"
  elif ([.providers[].windows[]?.used_percent // 0] | max // 0) >= 80 then "0xffeb6f92"
  elif ([.providers[].windows[]?.used_percent // 0] | max // 0) >= 50 then "0xfff6c177"
  else "0xff9ccfd8" end
' "$cache")

if [ "${1:-}" = popup ]; then
  sketchybar --set llm_usage.codex drawing=off --set llm_usage.opencode_go drawing=off --set llm_usage.claude_code drawing=off
  jq -r '
    def name: {"codex":"Codex", "opencode-go":"OpenCode Go", "claude-code":"Claude Code"}[.] // .;
    def pad($width): . as $text | $text + (" " * ([0, ($width - ($text | length))] | max));
    .providers[] |
    select(.status != "unavailable") |
    . as $p |
    "\($p.provider | name | pad(12))  \([$p.windows[] | select(.used_percent != null) | ((.used_percent | round | tostring) + "%" | pad(4)) + " " + (.label | pad(3))] | join("  "))"
  ' "$cache" | while IFS= read -r line; do
    case "$line" in
      Codex*) item=llm_usage.codex ;;
      OpenCode\ Go*) item=llm_usage.opencode_go ;;
      Claude\ Code*) item=llm_usage.claude_code ;;
    esac
    sketchybar --set "$item" drawing=on label="$line"
  done
  freshness=$(jq -r '"Updated \(.fetched_at | strftime("%H:%M:%S"))"' "$cache")
  sketchybar --set llm_usage.freshness label="$freshness"
  sketchybar --set llm_usage popup.drawing=toggle
  exit 0
fi

sketchybar --set "$NAME" label="$summary" --set llm_usage_logo background.color="$color"
