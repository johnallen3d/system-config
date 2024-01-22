#! /usr/bin/env bash

# ❯ mpc-rs | jq
# {
#   state: "stop", or "play", or "pause"
#   artist: "", or "Phish"
#   title: "", or "Down with Disease"
# }

status=$(mpc-rs)

while IFS='=' read -r key value; do
	case "$key" in
	'volume') volume="$value" ;;
	'state') state="$value" ;;
	'artist') artist="$value" ;;
	'title') title="$value" ;;
	esac
done <<<"$status"

if [ "${state}" == "stop" ]; then
	output=""
	icon=""
else
	if [ "${state}" == "play" ]; then
		icon=""
	else
		icon=""
	fi

	output="${artist} • ${title}"
fi

# echo $status
# echo $state
# echo $output
# echo $artist
# echo $title
# echo $icon

sketchybar -m \
	--set mpd icon="${icon}" \
	--set mpd label="${output}"
