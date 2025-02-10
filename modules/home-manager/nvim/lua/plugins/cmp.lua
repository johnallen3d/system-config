return {
	"saghen/blink.cmp",

	dependencies = {
		"ribru17/blink-cmp-spell",
		"mikavilpas/blink-ripgrep.nvim",

		{
			"kristijanhusak/vim-dadbod-completion",
			ft = { "sql", "mysql", "plsql" },
			lazy = true,
		},

		{ "moyiz/blink-emoji.nvim", ft = "md" },
	},

	opts = {
		keymap = {
			preset = "default",
			["<C-f>"] = { "select_and_accept" },
			cmdline = {
				preset = "default",
				["<C-f>"] = { "select_and_accept", "fallback" },
			},
		},

		completion = {
			menu = {
				border = "rounded",
			},
			documentation = {
				auto_show = true,
				auto_show_delay_ms = 0,
				window = {
					border = "rounded",
				},
			},
		},

		sources = {
			default = {
				"lsp",
				"path",
				"buffer",
				"ripgrep",
				"spell",
				"emoji",
				"dadbod",
			},
			cmdline = { "cmdline" },
			per_filetype = {
				codecompanion = {
					"codecompanion",
					"lsp",
					"path",
					"buffer",
					"ripgrep",
					"emoji",
				},
			},
			providers = {
				dadbod = {
					module = "vim_dadbod_completion.blink",
					name = "dadbod",
				},
				spell = {
					module = "blink-cmp-spell",
					name = "spell",
				},
				emoji = {
					module = "blink-emoji",
					name = "emoji",
				},
				ripgrep = {
					module = "blink-ripgrep",
					name = "ripgrep",
					score_offset = -10,
				},
			},
		},

		fuzzy = {
			sorts = {
				function(a, b)
					local sort = require("blink.cmp.fuzzy.sort")
					if a.source_id == "spell" and b.source_id == "spell" then
						return sort.label(a, b)
					end
				end,
				-- This is the normal default order, which we fall back to
				"score",
				"kind",
				"label",
			},
		},
	},
}
