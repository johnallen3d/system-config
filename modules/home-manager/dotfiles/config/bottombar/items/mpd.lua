local colors = require("colors")

-- Sbar.add("item", "mpd_logo", {
-- 	label = {
-- 		drawing = false,
-- 	},
-- 	icon = {
-- 		string = "",
-- 		drawing = false,
-- 	},
-- 	background = {
-- 		color = colors.orange,
-- 		image = {
-- 			drawing = true,
-- 			-- scale = 1.25,
-- 		},
-- 	},
-- 	padding_left = 0,
-- 	position = "center",
-- })

local mpd = {
	icon = {
		drawing = true,
		color = colors.orange,
		padding_left = 24,
	},
	background = {
		height = 32,
		color = colors.bg1,
	},
	label = {
		string = "Loading…",
		padding_right = 24,
	},
	click_script = "osascript -e 'tell application \"Music\" to playpause'",
	position = "center",
	update_freq = 1,
	script = "~/.config/bottombar/plugins/music.sh",
}

Sbar.add("item", "mpd", mpd)

-- TODO: how to make this work
Sbar.add("event", "song_update", "com.apple.iTunes.playerInfo")
mpd:subscribe({ "mpd", "song_update" })

return { "mpd" }
