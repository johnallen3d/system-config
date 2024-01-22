local settings = require("settings")

Sbar.bar(settings.merge(settings.bar, {
	position = "top",
	y_offset = 6,
}))
