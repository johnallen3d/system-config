return {
	"saghen/blink.cmp",

	dependencies = {
		"moyiz/blink-emoji.nvim",
		"Kaiser-Yang/blink-cmp-dictionary",
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
				"copilot",
				"emoji",
			},
			cmdline = { "cmdline" },
			providers = {
				copilot = {
					name = "copilot",
					module = "blink-cmp-copilot",
					score_offset = -100,
					async = true,
				},
				dictionary = {
					module = "blink-cmp-dictionary",
					name = "dictionary",
				},
				emoji = {
					module = "blink-emoji",
					name = "emoji",
					score_offset = 10,
				},
			},
		},
	},
}
