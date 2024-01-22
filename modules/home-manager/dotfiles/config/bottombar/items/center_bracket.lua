local items = require("items.mpd")
local settings = require("settings")

Sbar.add(
	"bracket",
	items,
	settings.merge(settings.bracket, {
		position = "right",
	})
)
