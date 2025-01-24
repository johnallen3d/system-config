return {
	"folke/snacks.nvim",
	opts = {
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
