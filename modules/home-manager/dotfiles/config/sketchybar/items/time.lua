local colors = require("colors")
local settings = require("settings")

local time = Sbar.add(
	"item",
	"time",
	settings.merge(settings.item.right, {
		update_freq = 15,
	})
)

local function update()
	time:set({ label = os.date("%H:%M") })
end

time:subscribe("routine", update)
time:subscribe("forced", update)

Sbar.add("item", "time_logo", {
	icon = {
		string = "",
		width = settings.logo.size,
		align = "center",
	},
	background = {
		color = colors.cyan,
		height = settings.logo.size,
	},
	label = {
		drawing = false,
	},
	position = "right",
})

return { "time", "time_logo" }
