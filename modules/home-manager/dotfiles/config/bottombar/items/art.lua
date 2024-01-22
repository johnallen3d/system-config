local colors = require("colors")

local popup_toggle = "bottombar --set $NAME popup.drawing=toggle"

local art = Sbar.add("item", "mpd_logo", {
	label = {
		drawing = false,
	},
	icon = {
		drawing = false,
	},
	background = {
		color = colors.transparent,
		image = {
			drawing = true,
			scale = 0.33,
		},
	},
	padding_left = 0,
	position = "center",
	click_script = popup_toggle,
	popup = {
		-- drawing = false,
		align = "center",
		height = 256,
		y_offset = -10,
		background = {
			image = {
				scale = 0.75,
			},
			color = colors.bg1,
		},
	},
})

local popup = Sbar.add("item", "mpd_cover", {
	position = "popup." .. art.name,
	label = { drawing = false },
	icon = { drawing = false },
	background = {
		drawing = true,
		image = "/tmp/cover-large.png",
		color = colors.bg1,
		padding_left = -256,
		padding_right = 24,
	},
})
