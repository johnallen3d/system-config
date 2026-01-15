local colors = require("colors")

-- Repeat indicator - green widget with dark icon
Sbar.add("item", "music_repeat", {
	icon = {
		drawing = false,
		string = "\u{f363}", -- FA repeat icon
		font = "Font Awesome 6 Pro:Regular:14.0",
		color = colors.bg1,
		width = 28,
		align = "center",
	},
	background = {
		height = 28,
		color = colors.green,
		corner_radius = 6,
	},
	label = {
		drawing = false,
	},
	padding_left = 4,
	padding_right = 0,
	position = "center",
})

-- Shuffle indicator - grey widget with dark icon
Sbar.add("item", "music_shuffle", {
	icon = {
		drawing = false,
		string = "\u{f074}", -- FA shuffle icon
		font = "Font Awesome 6 Pro:Regular:14.0",
		color = colors.bg1,
		width = 28,
		align = "center",
	},
	background = {
		height = 28,
		color = colors.grey,
		corner_radius = 6,
	},
	label = {
		drawing = false,
	},
	padding_left = 4,
	padding_right = 0,
	position = "center",
})

return { "music_repeat", "music_shuffle" }
