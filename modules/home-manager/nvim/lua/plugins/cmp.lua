return {
	"saghen/blink.cmp",

	dependencies = {
		"Kaiser-Yang/blink-cmp-dictionary",
		"mikavilpas/blink-ripgrep.nvim",
		"olimorris/codecompanion.nvim",

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
				"codecompanion",
				"emoji",
				"dadbod",
			},
			cmdline = { "cmdline" },
			providers = {
				codecompanion = {
					name = "CodeCompanion",
					module = "codecompanion.providers.completion.blink",
					score_offset = -100,
					enabled = true,
				},
				dadbod = {
					name = "Dadbod",
					module = "vim_dadbod_completion.blink",
				},
				dictionary = {
					module = "blink-cmp-dictionary",
					name = "dictionary",
				},
				emoji = {
					module = "blink-emoji",
					name = "emoji",
				},
				ripgrep = {
					module = "blink-ripgrep",
					name = "Ripgrep",
					score_offset = -10,
				},
			},
		},
	},
}
