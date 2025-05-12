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

			-- play nice with oil.nvim
			-- https://github.com/folke/snacks.nvim/issues/1814#issuecomment-2865194886
			main = {
				file = false,
				current = true,
			},

			sources = {
				files = {
					hidden = true,
				},
				grep = {
					hidden = true,
				},
			},

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
