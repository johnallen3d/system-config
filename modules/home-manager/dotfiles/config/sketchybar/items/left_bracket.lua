local settings = require("settings")
-- local apple = require("items.apple")
local app_items = require("items.front_app")

local items = settings.flatten({
	-- apple,
	app_items,
})

Sbar.add("bracket", items, settings.bracket)
