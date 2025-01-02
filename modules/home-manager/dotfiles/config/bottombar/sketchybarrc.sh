#!/usr/bin/env bash

# tokyonight-moon
bracket_background_color="0xff222436"
default_label_color="0xffc8d3f5"
default_icon_color="0xffc8d3f5"
highlight_icon_color="0xffc3e88d"
bracket_border_color="${transparent_color}"
current_app_background_color="0xff82aaff"
current_app_color="0xff1b1d2b"
music_highlight="0xffc3e88d"
cpu_highlight="0xff82aaff"
weather_highlight="0xffffc777"
date_highlight="0xffc099ff"
time_highlight="0xff86e1fc"

#
# fonts
#
default_icon_font="Font Awesome 6 Pro:Regular:14.0"
default_label_font="Cascadia Code PL:SemiBold:14.0"
brand_font="Font Awesome 6 Brands:Regular:14.0"
# duotone_font="Font Awesome 6 Duotone:Solid:14.0"

#
# variables
#
plugins="$HOME/.config/bottombar/plugins"

############## BAR ##############
bottombar --bar \
	height=36 \
	y_offset=3 \
	blur_radius=0 \
	position=bottom \
	padding_left=12 \
	padding_right=12 \
	margin=0 \
	corner_radius=0 \
	color=$transparent_color \
	shadow=off

bottombar --default \
	icon.color="${default_icon_color}" \
	icon.font="${default_icon_font}" \
	icon.highlight_color="${highlight_icon_color}" \
	icon.padding_left=6 \
	icon.padding_right=6 \
	label.color="${default_label_color}" \
	label.font="${default_label_font}" \
	label.padding_left=6 \
	label.padding_right=6 \
	background.height=24 \
	background.padding_right=4 \
	background.padding_left=4 \
	background.corner_radius=5 \
	updates=when_shown

###################### FLOAT ###################
mpd_location="center"

bottombar \
	--add item mpd_logo $mpd_location \
	--set mpd_logo \
	icon= \
	label.drawing=off \
	icon.color=$current_app_color \
	background.color=$music_highlight

bottombar \
	--add item mpd $mpd_location \
	--set mpd \
	icon.drawing=on \
	icon.color=$music_highlight \
	update_freq=1 \
	click_script="mpc toggle" \
	background.color=$transparent_color

bottombar \
	--add bracket mpd_bracket \
	mpd_logo \
	mpd \
	--set mpd_bracket \
	background.color=$bracket_background_color \
	background.border_color=$bracket_border_color \
	background.border_width=3 \
	background.corner_radius=8 \
	background.height=32

pgrep mpd-updater | xargs kill -9
./plugins/mpd-updater &

echo "bottombar config loaded"
