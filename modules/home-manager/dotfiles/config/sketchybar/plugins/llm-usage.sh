#!/usr/bin/env bash
set -u

cache="@usageJson@"

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
