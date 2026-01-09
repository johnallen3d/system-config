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
		image = {
			drawing = true,
			scale = 0.33,
		},
	},
	padding_left = 16,
	padding_right = 0,
	position = "center",
})

return { "music_art" }
