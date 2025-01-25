return {
	"folke/snacks.nvim",
	opts = {
		scroll = { enabled = false },

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
