local colors = require("colors")

local _merge = function(t1, t2)
	for k, v in pairs(t2) do
		if type(v) == "table" then
			if type(t1[k] or false) == "table" then
				_merge(t1[k] or {}, t2[k] or {})
			else
				t1[k] = v
			end
		else
			t1[k] = v
		end
	end
	return t1
end

local _flatten = function(input)
	local flattened = {}

	local function sift(nested)
		for _, val in ipairs(nested) do
			if type(val) == "table" then
				sift(val)
			else
				table.insert(flattened, val)
			end
		end
	end

	sift(input)

	return flattened
end

return {
	bar = {
		height = 36,
		color = colors.transparent,
		shadow = true,
		sticky = true,
		padding_right = 12,
		padding_left = 12,
		blur_radius = 20,
		corner_radius = 0,
		topmost = "window",
	},
	font = {
		label = {
			family = "Cascadia Code PL",
			style = "SemiBold",
			size = 14.0,
		},
		icon = {
			family = "Font Awesome 6 Pro",
			style = "Regular",
			size = 14.0,
		},
		brand = {
			family = "Font Awesome 6 Brands",
			style = "Regular",
			size = 14.0,
		},
		nerd = {
			family = "Hack Nerd Font",
			style = "Bold",
			size = 22.0,
		},
	},
	padding = 6,
	item = {
		right = {
			background = {
				padding_left = 5,
			},
			icon = {
				drawing = false,
			},
			position = "right",
		},
		left = {
			background = {
				padding_left = 5,
			},
			icon = {
				drawing = false,
			},
			position = "left",
		},
	},
	icon = {
		right = {
			label = {
				drawing = false,
			},
			position = "right",
		},
		left = {
			label = {
				drawing = false,
			},
			position = "left",
		},
	},
	bracket = {
		background = {
			color = colors.bg1,
			border_color = colors.transparent,
			border_width = 3,
			corner_radius = 8,
			height = 32,
		},
	},
	logo = {
		size = 30,
	},
	merge = _merge,
	flatten = _flatten,
}
