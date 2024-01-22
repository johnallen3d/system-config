local colors = require("colors")
local settings = require("settings")

local date = Sbar.add(
	"item",
	"date",
	settings.merge(settings.item.right, {
		update_freq = 1000,
	})
)

local function update()
	date:set({ label = os.date("%Y-%m-%d") })
end

date:subscribe("routine", update)
date:subscribe("forced", update)

Sbar.add("item", "date_logo", {
	icon = {
		string = "",
		width = settings.logo.size,
		align = "center",
	},
	background = {
		color = colors.magenta,
		height = settings.logo.size,
	},
	label = {
		drawing = false,
	},
	position = "right",
})

return { "date", "date_logo" }
