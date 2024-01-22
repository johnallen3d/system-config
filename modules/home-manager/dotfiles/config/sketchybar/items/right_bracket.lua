local settings = require("settings")

local time = require("items.time")
local date = require("items.date")
local weather = require("items.weather")
local cpu = require("items.cpu")

local items = settings.flatten({
	time,
	date,
	weather,
	cpu,
})

Sbar.add(
	"bracket",
	items,
	settings.merge(settings.bracket, {
		position = "right",
	})
)
