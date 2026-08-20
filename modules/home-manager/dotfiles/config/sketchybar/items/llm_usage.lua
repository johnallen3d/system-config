local colors = require("colors")
Sbar.add("item", "llm_usage_logo", {
	position = "left",
	icon = {
		string = "AI",
		font = { family = "Cascadia Code PL", style = "Bold", size = 11.0 },
		width = 30,
		align = "center",
	},
	label = { drawing = false },
	background = { color = colors.red, height = 30 },
	padding_right = 1,
})

Sbar.add("item", "llm_usage", {
	position = "left",
	icon = { drawing = false },
	background = { padding_left = 5 },
	popup = {
		align = "left",
		background = { color = colors.bg1, border_color = colors.grey, border_width = 1, corner_radius = 6 },
	},
	update_freq = 60,
	script = "~/.config/sketchybar/plugins/llm-usage.sh",
	click_script = "~/.config/sketchybar/plugins/llm-usage.sh popup",
})

for _, provider in ipairs({ "codex", "opencode_go", "claude_code", "freshness" }) do
	Sbar.add("item", "llm_usage." .. provider, {
		position = "popup.llm_usage",
		label = { string = "Loading…", font = { size = 12.0 }, padding_left = 10, padding_right = 10 },
		background = { drawing = false },
	})
end

