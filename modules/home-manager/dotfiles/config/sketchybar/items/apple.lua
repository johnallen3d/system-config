-- local icons = require("icons")
local colors = require("colors")

-- local popup_toggle = "sketchybar --set $NAME popup.drawing=toggle"
local popup_toggle = "echo $NAME"

local apple_logo = Sbar.add("item", {
	padding_right = 15,
	click_script = popup_toggle,
	icon = {
		string = "x",
		font = {
			style = "Black",
			size = 16.0,
		},
		color = colors.green,
	},
	label = {
		drawing = false,
	},
	popup = {
		height = 35,
	},
})

local apple_prefs = Sbar.add("item", {
	position = "popup." .. apple_logo.name,
	icon = "y",
	label = "Preferences",
})

apple_prefs:subscribe("mouse.clicked", function(_)
	os.execute("open -a 'System Preferences'")
	apple_logo:set({ popup = { drawing = false } })
end)

return { apple_logo.name }
