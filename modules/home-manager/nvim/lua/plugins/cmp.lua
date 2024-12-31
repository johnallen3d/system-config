return {
	"saghen/blink.cmp",

	dependencies = {
		{ "Allaman/emoji.nvim", opts = { enable_cmp_integration = true } },
		{
			"saghen/blink.compat",
			opts = {
				impersonate_nvim_cmp = true,
				enable_events = true,
				debug = true,
			},
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
			default = { "lsp", "path", "buffer", "emoji", "dadbod" },
			cmdline = { "cmdline" },
			compat = { "emoji" },
		},
	},
}
