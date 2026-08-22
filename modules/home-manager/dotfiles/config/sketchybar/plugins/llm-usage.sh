#!/usr/bin/env bash
set -u

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/llm-usage"
cache="$cache_dir/usage.json"
lock="$cache_dir/refresh.lock"
bin="@llmUsageBin@"
timeout_bin="@timeoutBin@"
stat_bin="@statBin@"
fish_bin="@fishBin@"

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

summary=$(jq -r '
  def name: {"codex":"Codex", "opencode-go":"Go", "claude-code":"Claude"}[.] // .;
  def remaining:
    (.reset_at // null) as $reset |
    if $reset == null then ""
    else ($reset - now | floor) as $seconds |
      if $seconds <= 0 then "now"
      elif $seconds < 3600 then "\($seconds / 60 | floor)m"
      elif $seconds < 86400 then "\($seconds / 3600 | floor)h"
      else "\($seconds / 86400 | floor)d"
      end
    end;
  def exhausted: .status == "rate_limited";
  def exhausted_remaining: [.windows[] | select((.limit_reached or ((.used_percent // 0) >= 100)) and .reset_at != null)] | max_by(.reset_at) | remaining;
  .providers | map(
    select(.status != "unavailable") |
    . as $p |
    if ($p | exhausted) then "\($p.provider | name) -\($p | exhausted_remaining)"
    else
      [$p.windows[] | select(.used_percent != null) | "\(.used_percent | round)% \(.label)↻\(remaining)"] as $windows |
      "\($p.provider | name) \($windows | join(" "))"
    end
  ) | join(" · ")
' "$cache")

color=$(jq -r '
  [.providers[] | select(.status != "unavailable") | .status, (.windows[]?.status)] as $states |
  if ($states | index("rate_limited")) then "0xffeb6f92"
  elif ($states | index("unavailable")) then "0xfff6c177"
  elif ([.providers[] | select(.status == "ok") | .windows[]?.used_percent // 0] | max // 0) >= 80 then "0xffeb6f92"
  elif ([.providers[] | select(.status == "ok") | .windows[]?.used_percent // 0] | max // 0) >= 50 then "0xfff6c177"
  else "0xff9ccfd8" end
' "$cache")

if [ "${1:-}" = popup ]; then
  sketchybar --set llm_usage.codex drawing=off --set llm_usage.opencode_go drawing=off --set llm_usage.claude_code drawing=off
  jq -r '
    def name: {"codex":"Codex", "opencode-go":"OpenCode Go", "claude-code":"Claude Code"}[.] // .;
    def pad($width): . as $text | $text + (" " * ([0, ($width - ($text | length))] | max));
    def remaining:
      (.reset_at // null) as $reset |
      if $reset == null then ""
      else ($reset - now | floor) as $seconds |
        if $seconds <= 0 then " now"
        elif $seconds < 3600 then " \($seconds / 60 | floor)m"
        elif $seconds < 86400 then " \($seconds / 3600 | floor)h"
        else " \($seconds / 86400 | floor)d"
        end
      end;
    def exhausted: .status == "rate_limited";
    def exhausted_remaining: [.windows[] | select((.limit_reached or ((.used_percent // 0) >= 100)) and .reset_at != null)] | max_by(.reset_at) | remaining | ltrimstr(" ");
    .providers[] |
    select(.status != "unavailable") |
    . as $p |
    if ($p | exhausted) then "\($p.provider | name | pad(12))  -\($p | exhausted_remaining)"
    else "\($p.provider | name | pad(12))  \([$p.windows[] | select(.used_percent != null) | ((.used_percent | round | tostring) + "%" | pad(4)) + " " + (.label | pad(3)) + " ↻" + remaining] | join("  "))"
    end
  ' "$cache" | while IFS= read -r line; do
    case "$line" in
      Codex*) item=llm_usage.codex ;;
      OpenCode\ Go*) item=llm_usage.opencode_go ;;
      Claude\ Code*) item=llm_usage.claude_code ;;
      *) continue ;;
    esac
    sketchybar --set "$item" drawing=on label="$line"
  done
  freshness=$(jq -r '"Updated \(.fetched_at | strftime("%H:%M:%S")) · ↻ = reset in"' "$cache")
  sketchybar --set llm_usage.freshness label="$freshness"
  sketchybar --set llm_usage popup.drawing=toggle
  exit 0
else
  sketchybar --set llm_usage label="$summary" --set llm_usage_logo background.color="$color"
fi
