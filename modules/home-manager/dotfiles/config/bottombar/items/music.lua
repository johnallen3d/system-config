local colors = require("colors")

-- Music info item with play/pause icon
Sbar.add("item", "music", {
	icon = {
		drawing = true,
		string = "",
		color = colors.orange,
		padding_left = 8,
	},
	background = {
		height = 32,
		color = colors.bg1,
	},
	label = {
		string = "Loading…",
		padding_right = 8,
	},
	position = "center",
})

return { "music" }
