local colors = require("colors")
local settings = require("settings")

Sbar.add(
	"item",
	"weather",
	settings.merge(settings.item.right, {
		update_freq = 1800,
	})
)

Sbar.add(
	"item",
	"weather_logo",
	settings.merge(settings.icon.right, {
		icon = {
			font = settings.font.nerd,
			width = settings.logo.size,
			align = "center",
		},
		background = {
			color = colors.yellow,
			height = settings.logo.size,
		},
	})
)

return { "weather", "weather_logo" }
