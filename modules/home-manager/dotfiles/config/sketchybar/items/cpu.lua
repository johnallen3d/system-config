local colors = require("colors")
local settings = require("settings")

Sbar.add(
	"item",
	"cpu",
	settings.merge(settings.item.right, {
		update_freq = 5,
		script = "~/.config/sketchybar/plugins/cpu.sh",
	})
)

Sbar.add("item", "cpu_logo", {
	icon = {
		string = "",
		width = settings.logo.size,
		align = "center",
	},
	background = {
		color = colors.blue,
		height = settings.logo.size,
	},
	label = {
		drawing = false,
	},
	padding_left = 1,
	position = "right",
})

return { "cpu", "cpu_logo" }
