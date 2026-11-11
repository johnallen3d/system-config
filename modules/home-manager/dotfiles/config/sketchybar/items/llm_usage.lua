local colors = require("colors")

local app_font = { family = "sketchybar-app-font", style = "Regular", size = 15.0 }
local row_font = { family = "Cascadia Code PL", size = 12.0 }
local script = "~/.config/sketchybar/plugins/llm-usage.sh"

Sbar.add("item", "llm_usage_logo", {
	position = "left",
	icon = { string = ":claude:", font = app_font, width = 30, align = "center" },
	label = { drawing = false },
	background = { color = colors.red, height = 30 },
	padding_right = 1,
	click_script = script .. " popup",
})

-- `llm_usage` (work) owns the popup and the refresh script.
Sbar.add("item", "llm_usage", {
	position = "left",
	icon = { string = utf8.char(0xF0B1), padding_left = 8, padding_right = 4 },
	label = { padding_right = 4 },
	popup = {
		align = "left",
		background = { color = colors.bg1, border_color = colors.grey, border_width = 1, corner_radius = 6 },
	},
	update_freq = 60,
	script = script,
	click_script = script .. " popup",
})

Sbar.add("item", "llm_usage_personal", {
	position = "left",
	icon = { string = utf8.char(0xF015), padding_left = 8, padding_right = 4 },
	label = { padding_right = 6 },
	click_script = script .. " popup",
})

local accounts = { work = 0xF0B1, personal = 0xF015 }
local providers = { claude_code = ":claude:", codex = ":codex:", opencode_go = ":opencode:" }
for _, account in ipairs({ "work", "personal" }) do
	Sbar.add("item", "llm_usage." .. account, {
		position = "popup.llm_usage",
		icon = { string = utf8.char(accounts[account]), color = colors.white, padding_left = 10 },
		label = { string = "Loading…", font = row_font, color = colors.white, padding_right = 10 },
		background = { drawing = false },
	})
	for _, provider in ipairs({ "claude_code", "codex", "opencode_go" }) do
		Sbar.add("item", "llm_usage." .. account .. "_" .. provider, {
			position = "popup.llm_usage",
			drawing = false,
			icon = { string = providers[provider], font = app_font, color = colors.white, padding_left = 22, padding_right = 6 },
			label = { font = row_font, color = colors.white, padding_right = 10 },
			background = { drawing = false },
		})
	end
end
