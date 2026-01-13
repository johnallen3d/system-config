#!/usr/bin/env bash

# to avoid doing this👇
# export PATH="/usr/local/bin:$PATH"
# modify the plist file to be prefixed with `/usr/local/bin`
# /opt/homebrew/Cellar/sketchybar/[current-version]/homebrew.mxcl.sketchybar.plist

#
# colors
#
transparent_color="0x00000000"

# catppuccin-mocha
# default_label_color="0xffCDD6F4"
# default_icon_color="0xffCDD6F4"
# highlight_icon_color="0xff89b4fa"
# bracket_border_color="${transparent_color}"
# bracket_background_color="0xff313244"
# current_app_background_color="0xff89b4fa"
# current_app_color="0xff121219"
# music_highlight="0xffEDC4E5"
# time_highlight="0xffF5E3B5"
# date_highlitht="0xffb4befe"
# weather_highlight="0xffB3E1A7"
# cpu_highlight="0xffa6adc8"

# onedark-deep
# bracket_background_color="0xff1a212e"
# default_label_color="0xff93a4c3"
# default_icon_color="0xff93a4c3"
# highlight_icon_color="0xff8ebd6b"
# bracket_border_color="${transparent_color}"
# current_app_background_color="0xff41a7fc"
# current_app_color="0xff0c0e15"
# music_highlight="0xff8bcd5b"
# cpu_highlight="0xff41a7fc"
# weather_highlight="0xffefbd5d"
# date_highlight="0xffc75ae8"
# time_highlight="0xff34bfd0"

# tokyonight-moon
bracket_background_color="0xff222436"       # bg1
default_label_color="0xffc8d3f5"            # white
default_icon_color="0xffc8d3f5"             # white
highlight_icon_color="0xffc3e88d"           # green
bracket_border_color="${transparent_color}" # transparent
current_app_background_color="0xff82aaff"   # blue
current_app_color="0xff1b1d2b"              # black
music_highlight="0xffc3e88d"                # green
cpu_highlight="0xff82aaff"                  # blue
weather_highlight="0xffffc777"              # yellow
date_highlight="0xffc099ff"                 # magenta
time_highlight="0xff86e1fc"                 # cyan

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
plugins="$HOME/.config/sketchybar/plugins"
# display_count="$(yabai -m query --displays | jq -r 'length')"
display_count="$(system_profiler SPDisplaysDataType | grep -c Resolution)"

############## BAR ##############
sketchybar --bar \
	height=36 \
	y_offset=6 \
	blur_radius=0 \
	position=top \
	padding_left=12 \
	padding_right=12 \
	margin=0 \
	corner_radius=0 \
	color=$transparent_color \
	shadow=off

# ############## DEFAULTS ###############
sketchybar --default \
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

############## DISPLAY 1 ###############
sketchybar \
	--add item window_title_logo_display_1 left \
	--set window_title_logo_display_1 associated_display=1 \
	icon= \
	icon.color=$current_app_color \
	label.drawing=off \
	background.color=$current_app_background_color

sketchybar \
	--add event window_focus \
	--add event title_change \
	--add item window_title_display_1 left \
	--set window_title_display_1 associated_display=1 \
	icon.drawing=off \
	background.color=$transparent_color \
	script="$plugins/window_title.sh" \
	--subscribe window_title_display_1 \
	window_focus \
	front_app_switched \
	space_change \
	title_change

sketchybar \
	--add bracket primary_spaces_bracket \
	window_title_logo_display_1 \
	window_title_display_1 \
	--set primary_spaces_bracket \
	background.color=$bracket_background_color \
	background.border_color=$bracket_border_color \
	background.border_width=3 \
	background.corner_radius=8 \
	background.height=32

############## DISPLAY 2 ###############
scratch_space=5
terminal_space=6
flex=" "

# if [ "${display_count}" = "2" ]; then
# 	scratch_space=6
# 	terminal_space=7
# 	flex="flex"

# 	sketchybar \
# 		--add space flex left \
# 		--set flex associated_display=2 \
# 		label.drawing=off \
# 		associated_space=5 \
# 		icon=􏢺 \
# 		background.color=$transparent_color
# fi

sketchybar \
	--add item window_title_logo_display_2 left \
	--set window_title_logo_display_2 associated_display=2 \
	icon= \
	icon.color=$current_app_color \
	label.drawing=off \
	background.color=$current_app_background_color

sketchybar \
	--add event window_focus \
	--add event title_change \
	--add item window_title_display_2 left \
	--set window_title_display_2 associated_display=2 \
	icon.drawing=off \
	background.color=$transparent_color \
	script="$plugins/window_title.sh" \
	--subscribe window_title_display_2 \
	window_focus \
	front_app_switched \
	space_change \
	title_change

sketchybar \
	--add bracket secondary_spaces_bracket \
	window_title_logo_display_2 \
	window_title_display_2 \
	--set secondary_spaces_bracket \
	background.color=$bracket_background_color \
	background.border_color=$bracket_border_color \
	background.border_width=3 \
	background.corner_radius=8 \
	background.height=32

######################SHARED ###################
sketchybar \
	--add item time right \
	--set time update_freq=10 \
	icon.drawing=off \
	script="~/.config/sketchybar/plugins/time.sh" \
	background.color=$transparent_color \
	background.padding_left=5

sketchybar \
	--add item time_logo right \
	--set time_logo icon= \
	icon.color=$current_app_color \
	label.drawing=off \
	background.color=$time_highlight

sketchybar \
	--add item date right \
	--set date update_freq=1000 \
	icon.drawing=off \
	script="~/.config/sketchybar/plugins/date.sh" \
	background.color=$transparent_color \
	background.padding_left=5

sketchybar \
	--add item date_logo right \
	--set date_logo icon= \
	icon.color=$current_app_color \
	label.drawing=off \
	background.color=$date_highlight

# script="${plugins}/weather.sh" \
sketchybar \
	--add item weather right \
	--set weather \
	update_freq=1800 \
	icon.drawing=off \
	background.color=$transparent_color

# script="$HOME/.cargo/bin/conditions current" \

sketchybar \
	--add item weather_logo right \
	--set weather_logo icon= \
	icon.font="Hack Nerd Font:Regular:14.0" \
	icon.color=$current_app_color \
	label.drawing=off \
	background.color=$weather_highlight

sketchybar \
	--add item cpu right \
	--set cpu \
	icon.drawing=off \
	update_freq=5 \
	script="${plugins}/cpu.sh" \
	background.color=$transparent_color \
	click_script="open -a activity\ monitor"

sketchybar \
	--add item cpu_logo right \
	--set cpu_logo icon= \
	icon.color=$current_app_color \
	label.drawing=off \
	background.color=$cpu_highlight

sketchybar --add bracket right_bar_bracket \
	time \
	time_logo \
	date \
	date_logo \
	weather \
	weather_logo \
	cpu \
	cpu_logo \
	--set right_bar_bracket \
	background.color=$bracket_background_color \
	background.border_color=$bracket_border_color \
	background.border_width=3 \
	background.corner_radius=8 \
	background.height=36

###################### FINALIZE ###################
sketchybar -m --update

pgrep weather-updater | xargs kill -9
./plugins/weather-updater &

echo "sketchybar configuration loaded.."

exit 0
