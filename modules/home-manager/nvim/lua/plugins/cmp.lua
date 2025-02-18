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

		{
			"Kaiser-Yang/blink-cmp-git",
			dependencies = { "nvim-lua/plenary.nvim" },
		},

		{ "moyiz/blink-emoji.nvim", ft = "md" },
	},

	opts = {
		keymap = {
			preset = "default",
			["<C-f>"] = { "select_and_accept" },
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

		cmdline = {
			enabled = true,
			-- TODO: this should not be necessary any more
			-- https://github.com/LazyVim/LazyVim/pull/5620/files
			sources = { "cmdline" },
		},

		sources = {
			default = {
				"lsp",
				"git",
				"path",
				"buffer",
				"ripgrep",
				"spell",
				"emoji",
				"dadbod",
			},
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
				emoji = {
					module = "blink-emoji",
					name = "emoji",
				},
				git = {
					module = "blink-cmp-git",
					name = "git",
				},
				ripgrep = {
					module = "blink-ripgrep",
					name = "ripgrep",
					score_offset = -10,
				},
				spell = {
					module = "blink-cmp-spell",
					name = "spell",
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
