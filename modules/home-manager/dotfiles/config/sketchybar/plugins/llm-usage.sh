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

popup_rows() {
  jq -r '
    def reset_in:
      ((.reset_at - now | floor) as $seconds |
        if $seconds <= 0 then "now"
        elif $seconds >= 86400 then "\($seconds / 86400 | floor)d"
        elif $seconds >= 3600 then "\($seconds / 3600 | floor)h"
        else "\($seconds / 60 | floor)m"
        end);
    def lpad($width):
      tostring as $text | (" " * ([$width - ($text | length), 0] | max)) + $text;
    def rpad($width):
      tostring as $text | $text + (" " * ([$width - ($text | length), 0] | max));
    def window_text($label):
      ([.windows[] | select(.label == $label and .status != "unavailable" and .used_percent != null)] | first) |
      if . == null then " " * 13
      else "\(.label | lpad(3)) \(("\(.used_percent | round)%") | lpad(4)) \((if .reset_at then "↻\(reset_in)" else "" end) | rpad(4))"
      end;
    .providers[] | select(.status != "unavailable" and .display.capacity_used_percent != null) |
      [.provider, .display.name, window_text("5h"), window_text("7d"), window_text("30d"),
       (if .status == "stale" then " (stale)" else "" end)] | @tsv
  ' "${1:-$cache}" |
    while IFS=$'\t' read -r provider name five_hour seven_day thirty_day stale; do
      label=$(printf '%-12s %s %s' "$name" "$five_hour" "$seven_day")
      [ "$thirty_day" = "             " ] || label="$label $thirty_day"
      printf '%s\t%s%s\n' "${provider//-/_}" "$label" "$stale"
    done
}

if [ "${1:-}" = "--test" ]; then
  [ "$(color_for_severity ok)" = "0xff9ccfd8" ] || exit 1
  [ "$(color_for_severity warning)" = "0xfff6c177" ] || exit 1
  [ "$(color_for_severity critical)" = "0xffeb6f92" ] || exit 1
  [ "$(color_for_severity unknown)" = "0xfff6c177" ] || exit 1
  test_cache=$(mktemp)
  printf '%s' '{"providers":[{"provider":"codex","status":"ok","windows":[{"label":"5h","status":"ok","used_percent":62},{"label":"7d","status":"ok","used_percent":18}],"display":{"name":"Codex","capacity_used_percent":62,"limiting_window":{"label":"5h","used_percent":62}}},{"provider":"opencode-go","status":"ok","windows":[{"label":"5h","status":"ok","used_percent":4}],"display":{"name":"OpenCode Go","capacity_used_percent":4,"limiting_window":{"label":"5h","used_percent":4}}},{"provider":"claude-code","status":"stale","windows":[{"label":"5h","status":"unavailable"},{"label":"7d","status":"ok","used_percent":23}],"display":{"name":"Claude Code","capacity_used_percent":23,"limiting_window":{"label":"7d","used_percent":23}}}]}' >"$test_cache"
  [ "$(popup_rows "$test_cache")" = $'codex\tCodex         5h  62%       7d  18%     \nopencode_go\tOpenCode Go   5h   4%                   \nclaude_code\tClaude Code                 7d  23%      (stale)' ] || exit 1
  rm -f "$test_cache"
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

summary=$(jq -r '.presentation.summary' "$cache")
severity=$(jq -r '.presentation.severity' "$cache")
color=$(color_for_severity "$severity")

if [ "${1:-}" = popup ]; then
  sketchybar --set llm_usage.codex drawing=off --set llm_usage.opencode_go drawing=off --set llm_usage.claude_code drawing=off
  popup_rows |
    while IFS=$'\t' read -r provider label; do
      case "$provider" in
        codex|opencode_go|claude_code) ;;
        *) continue ;;
      esac
      sketchybar --set "llm_usage.$provider" drawing=on label="$label"
    done
  freshness=$(jq -r '.presentation.freshness' "$cache")
  sketchybar --set llm_usage.freshness label="$freshness"
  sketchybar --set llm_usage popup.drawing=toggle
  exit 0
fi

sketchybar --set llm_usage label="$summary" --set llm_usage_logo background.color="$color"
