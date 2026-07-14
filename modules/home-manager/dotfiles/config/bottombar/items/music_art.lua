local colors = require("colors")

-- Album art item
Sbar.add("item", "music_art", {
	label = {
		drawing = false,
	},
	icon = {
		drawing = false,
	},
	background = {
		color = colors.transparent,
		height = 12,
		image = {
			drawing = true,
			scale = 0.03,
		},
	},
	padding_left = 16,
	padding_right = 0,
	position = "center",
})

return { "music_art" }
