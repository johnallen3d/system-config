local settings = require("settings")
-- local apple = require("items.apple")
local app_items = require("items.front_app")
local llm_usage = { "llm_usage_logo", "llm_usage" }

local items = settings.flatten({
	-- apple,
	llm_usage,
	app_items,
})

Sbar.add("bracket", items, settings.bracket)
