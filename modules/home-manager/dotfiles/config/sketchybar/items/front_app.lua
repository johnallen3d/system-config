local colors = require("colors")
local settings = require("settings")

Sbar.add(
	"item",
	"front_app_logo",
	settings.merge(settings.icon.left, {
		icon = {
			string = "",
			width = settings.logo.size,
			align = "center",
		},
		background = {
			color = colors.green,
			height = settings.logo.size,
		},
		padding_left = 1,
	})
)

local front_app = Sbar.add(
	"item",
	"front_app",
	settings.merge(settings.item.left, {
		update_freq = 5,
	})
)

front_app:subscribe("front_app_switched", function(env)
	front_app:set({
		label = {
			string = env.INFO,
		},
	})
end)

return { "front_app_logo", "front_app" }
