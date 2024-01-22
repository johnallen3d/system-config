local settings = require("settings")
local colors = require("colors")

Sbar.default({
	updates = "when_shown",
	icon = {
		font = settings.font.icon,
		color = colors.bg1,
		padding_left = settings.padding,
		padding_right = settings.padding,
	},
	label = {
		font = settings.font.label,
		color = colors.white,
		padding_left = settings.padding,
		padding_right = settings.padding,
	},
	background = {
		height = 24,
		corner_radius = 5,
		padding_left = 4,
		padding_right = 4,
	},
})
