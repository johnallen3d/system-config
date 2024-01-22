local settings = require("settings")

Sbar.bar(settings.merge(settings.bar, {
	height = 42,
	position = "bottom",
	y_offset = 3,
}))
