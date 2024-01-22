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

Sbar.add("item", "mpd", {
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
	click_script = "mp-cli --format=none toggle",
	position = "center",
})

return { "mpd_logo", "mpd" }
