#!/usr/bin/env bash
set -u

work_cache="@workUsageJson@"
personal_cache="@personalUsageJson@"
accounts=(work personal)
providers=(claude_code codex opencode_go)

cache_for() {
  case "$1" in
    work) printf '%s\n' "$work_cache" ;;
    personal) printf '%s\n' "$personal_cache" ;;
  esac
}

title_for() {
  case "$1" in
    work) printf '%s\n' Work ;;
    personal) printf '%s\n' Personal ;;
  esac
}

color_for_severity() {
  case "$1" in
    ok) printf '%s\n' '0xff9ccfd8' ;;
    critical) printf '%s\n' '0xffeb6f92' ;;
    *) printf '%s\n' '0xfff6c177' ;;
  esac
}

jq_defs='
  def reset_in:
    ((.reset_at - now | floor) as $seconds |
      if $seconds <= 0 then "now"
      elif $seconds >= 86400 then "\($seconds / 86400 | floor)d"
      elif $seconds >= 3600 then "\($seconds / 3600 | floor)h"
      else "\($seconds / 60 | floor)m"
      end);
'

# Prints "<severity>\t<label>" for the account's Claude Code quota. The label
# uses the most-used window, since that is the one closest to blocking work.
claude_summary() {
  local cache="$1"
  if [ ! -r "$cache" ]; then
    printf 'unknown\t–\n'
    return
  fi
  jq -r "$jq_defs"'
    ([.providers[]? | select(.provider == "claude-code")] | first) as $p |
    if $p == null or $p.status == "unavailable" or $p.display.capacity_used_percent == null then
      "unknown\t–"
    else
      ($p.display.windows | max_by(.used_percent)) as $w |
      (if $p.display.exhausted then 100 else ($w.used_percent // 0) end) as $used |
      (if $used >= 90 then "critical" elif $used >= 70 then "warning" else "ok" end) as $severity |
      "\($severity)\t\($used)%\(if $w.reset_at then " ↻\($w | reset_in)" else "" end)\(if $p.status == "stale" then " ≈" else "" end)"
    end
  ' "$cache" 2>/dev/null || printf 'unknown\t–\n'
}

popup_rows() {
  jq -r "$jq_defs"'
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
      [.provider, window_text("5h"), window_text("7d"), window_text("30d"),
       (if .status == "stale" then " (stale)" else "" end)] | @tsv
  ' "$1" |
    while IFS=$'\t' read -r provider five_hour seven_day thirty_day stale; do
      label="$five_hour $seven_day"
      [ "$thirty_day" = "             " ] || label="$label $thirty_day"
      printf '%s\t%s%s\n' "${provider//-/_}" "$label" "$stale"
    done
}

updated_at() {
  jq -r '.fetched_at | if . then "\(localtime | strftime("%H:%M:%S"))" else "no data" end' "$1" 2>/dev/null ||
    printf '%s\n' 'no data'
}

if [ "${1:-}" = popup ]; then
  args=()
  for account in "${accounts[@]}"; do
    cache=$(cache_for "$account")
    for provider in "${providers[@]}"; do
      args+=(--set "llm_usage.${account}_$provider" drawing=off)
    done
    if [ -r "$cache" ]; then
      args+=(--set "llm_usage.$account" label="$(title_for "$account") $(updated_at "$cache")")
      while IFS=$'\t' read -r provider label; do
        case " ${providers[*]} " in
          *" $provider "*) args+=(--set "llm_usage.${account}_$provider" drawing=on label="$label") ;;
        esac
      done < <(popup_rows "$cache")
    else
      args+=(--set "llm_usage.$account" label="$(title_for "$account") no data")
    fi
  done
  sketchybar "${args[@]}" --set llm_usage popup.drawing=toggle
  exit 0
fi

rank() {
  case "$1" in
    critical) echo 3 ;;
    warning|unknown) echo 2 ;;
    *) echo 1 ;;
  esac
}

worst=ok
args=()
for account in "${accounts[@]}"; do
  IFS=$'\t' read -r severity label < <(claude_summary "$(cache_for "$account")")
  [ "$(rank "$severity")" -gt "$(rank "$worst")" ] && worst=$severity
  item=llm_usage
  [ "$account" = work ] || item="llm_usage_$account"
  args+=(--set "$item" label="$label" icon.color="$(color_for_severity "$severity")")
done

sketchybar "${args[@]}" --set llm_usage_logo background.color="$(color_for_severity "$worst")"
