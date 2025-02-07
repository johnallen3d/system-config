return {
	"folke/snacks.nvim",
	opts = {
		scroll = { enabled = false },

		indent = {
			chunk = {
				enabled = true,
			},
		},
		picker = {
			layout = "vscode",

			win = {
				input = {
					keys = {
						["<Esc>"] = { "close", mode = { "n", "i" } },
					},
				},
			},
		},
	},
}
