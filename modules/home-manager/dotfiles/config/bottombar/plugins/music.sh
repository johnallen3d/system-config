#! /usr/bin/env bash

# ❯ mp-cli --format text
# volume=91
# state=pause
# artist=Grateful Dead
# album=One From The Vault (Disc 1) [Live]
# title=Introduction
# position=0
# queue_count=16
# elapsed=00:19
# track_length=00:47
# repeat=off
# random=off
# single=off
# consume=off

# status=$(mp-cli --format text)

# while IFS='=' read -r key value; do
# 	case "$key" in
# 	'volume') volume="$value" ;;
# 	'state') state="$value" ;;
# 	'artist') artist="$value" ;;
# 	'album') album="$value" ;;
# 	'title') title="$value" ;;
# 	'elapsed') elapsed="$value" ;;
# 	'track_length') track_length="$value" ;;
# 	esac
# done <<<"$status"

# if [ "${state}" == "stop" ]; then
# 	output=""
# 	icon=""
# else
# 	if [ "${state}" == "play" ]; then
# 		icon=""
# 	else
# 		icon=""
# 	fi

# 	output="${title} • ${artist} • ${album} [${elapsed}/${track_length}]"
# fi

# output="${title} • ${artist} • ${album} [${elapsed}/${track_length}]"

# bottombar -m \
#   --set mpd icon="${icon}" \
#   --set mpd label="${output}"

#!/usr/bin/env bash

# FIXME: Running an osascript on an application target opens that app
# This sleep is needed to try and ensure that theres enough time to
# quit the app before the next osascript command is called. I assume
# com.apple.iTunes.playerInfo fires off an event when the player quits
# so it imediately runs before the process is killed
sleep 1

APP_STATE=$(pgrep -x Music)
if [[ ! $APP_STATE ]]; then
  sketchybar -m --set music drawing=off
  exit 0
fi

PLAYER_STATE=$(osascript -e "tell application \"Music\" to set playerState to (get player state) as text")
if [[ $PLAYER_STATE == "stopped" ]]; then
  sketchybar --set music drawing=off
  exit 0
fi

format_time() {
  local total_seconds=$1
  total_seconds=${total_seconds%.*}
  local minutes=$((total_seconds / 60))
  local seconds=$((total_seconds % 60))
  printf "%02d:%02d" $minutes $seconds
}

title=$(osascript -e 'tell application "Music" to get name of current track')
artist=$(osascript -e 'tell application "Music" to get artist of current track')
album=$(osascript -e 'tell application "Music" to get album of current track')
elapsed=$(osascript -e 'tell application "Music" to get player position')
track_length=$(osascript -e 'tell application "Music" to get duration of current track')

if [[ $PLAYER_STATE == "paused" ]]; then
  icon=""
fi

if [[ $PLAYER_STATE == "playing" ]]; then
  icon=""
fi

elapsed=$(format_time "$elapsed")
track_length=$(format_time "$track_length")

output="${title} • ${artist} • ${album} [${elapsed}/${track_length}]"

bottombar -m \
  --set mpd icon="${icon}" \
  --set mpd label="${output}" \
  --set mpd drawing=on
