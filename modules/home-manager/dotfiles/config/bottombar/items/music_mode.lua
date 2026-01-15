local colors = require("colors")

-- Music mode indicators (repeat/shuffle) using Font Awesome
Sbar.add("item", "music_mode", {
	icon = {
		drawing = false,
		string = "",
		font = "Font Awesome 6 Pro:Regular:14.0",
		color = colors.white,
		padding_left = 8,
		padding_right = 8,
	},
	background = {
		height = 32,
		color = colors.bg1,
	},
	label = {
		drawing = false,
	},
	position = "center",
})

return { "music_mode" }
