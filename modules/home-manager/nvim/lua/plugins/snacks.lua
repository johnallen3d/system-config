return {
	"folke/snacks.nvim",
	opts = {
		dashboard = { enabled = false },
		scroll = { enabled = false },

		image = { enabled = false },

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

	keys = {
		{
			"<leader>sl",
			'<cmd>lua Snacks.picker.lsp_symbols({layout = {preset = "vscode", preview = "main"}})<CR>',
			desc = "LSP Symbols picker",
		},
	},
}
