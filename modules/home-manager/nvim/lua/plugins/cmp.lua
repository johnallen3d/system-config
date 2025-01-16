return {
	"saghen/blink.cmp",

	dependencies = {
		"Kaiser-Yang/blink-cmp-dictionary",
		"moyiz/blink-emoji.nvim",
		"mikavilpas/blink-ripgrep.nvim",
		{
			"kristijanhusak/vim-dadbod-completion",
			ft = { "sql", "mysql", "plsql" },
			lazy = true,
		},
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
				"copilot",
				"emoji",
				"dadbod",
			},
			cmdline = { "cmdline" },
			providers = {
				copilot = {
					name = "copilot",
					module = "blink-cmp-copilot",
					score_offset = -100,
					async = true,
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
					score_offset = -25,
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
