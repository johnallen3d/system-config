return {
	"saghen/blink.cmp",

	dependencies = {
		"milanglacier/minuet-ai.nvim",

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

	-- forced to move from setting `opts` to `config` in order to wire up the
	-- `minuet` keymap
	config = function()
		require("blink.cmp").setup({
			keymap = {
				preset = "default",
				["<C-f>"] = { "select_and_accept" },
				-- manually invoke minuet completion.
				["<A-y>"] = require("minuet").make_blink_map(),
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
				-- from minuet.ai README
				-- recommended to avoid unnecessary request
				trigger = { prefetch_on_insert = false },
			},

			cmdline = {
				enabled = true,
				completion = { menu = { auto_show = true } },
				keymap = {
					preset = "default",
					["<C-f>"] = { "select_and_accept" },
				},
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
					"minuet",
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
					minuet = {
						name = "minuet",
						module = "minuet.blink",
						score_offset = -20,
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
						if
							a.source_id == "spell"
							and b.source_id == "spell"
						then
							return sort.label(a, b)
						end
					end,
					-- This is the normal default order, which we fall back to
					"score",
					"kind",
					"label",
				},
			},
		})
	end,
}
