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
			cmdline = { "lsp", "path" }, -- "help"
			compat = { "emoji" },
		},
	},
}

-- return {
-- 	{
-- 		"hrsh7th/nvim-cmp",
-- 		dependencies = {
-- 			"dmitmel/cmp-cmdline-history",
-- 			"hrsh7th/cmp-cmdline",
-- 			"hrsh7th/cmp-emoji",
-- 			-- "sourcegraph/sg.nvim",
-- 		},
-- 		---@param opts cmp.ConfigSchema
-- 		opts = function(_, opts)
-- 			local cmp = require("cmp")

-- 			opts.sources = cmp.config.sources(vim.list_extend(opts.sources, {
-- 				{ name = "cody", priority = 1001 },
-- 				{ name = "codeium", priority = 1002 },
-- 				{ name = "emoji" },
-- 			}))

-- 			-- replicate LazyVim mappings in order to override desired mappings
-- 			-- https://github.com/LazyVim/LazyVim/discussions/1433#discussioncomment-6959614
-- 			opts.mapping = cmp.mapping.preset.insert({
-- 				["<C-n>"] = cmp.mapping.select_next_item({
-- 					behavior = cmp.SelectBehavior.Insert,
-- 				}),
-- 				["<C-p>"] = cmp.mapping.select_prev_item({
-- 					behavior = cmp.SelectBehavior.Insert,
-- 				}),
-- 				["<C-f>"] = cmp.mapping.confirm({ select = true }), -- Accept currently selected item. Set `select` to `false` to only confirm explicitly selected items.
-- 				["<C-e>"] = cmp.mapping.abort(),
-- 				["<Down>"] = cmp.mapping.abort(),
-- 				["<Up>"] = cmp.mapping.abort(),
-- 			})

-- 			opts.window = {
-- 				completion = cmp.config.window.bordered(),
-- 				documentation = cmp.config.window.bordered(),
-- 			}

-- 			cmp.setup.cmdline(":", {
-- 				mapping = cmp.mapping.preset.cmdline({
-- 					["<C-f>"] = {
-- 						c = cmp.mapping.confirm({ select = true }),
-- 					},
-- 				}),
-- 				sources = {
-- 					{ name = "cmdline" },
-- 					{ name = "cmdline_history" },
-- 					{ name = "path" },
-- 				},
-- 			})

-- 			cmp.setup.cmdline("/", {
-- 				mapping = cmp.mapping.preset.cmdline({
-- 					["<C-f>"] = { c = cmp.mapping.confirm({ select = true }) }, -- Accept currently selected item. Set `select` to `false` to only confirm explicitly selected items.
-- 				}),
-- 				sources = {
-- 					{ name = "buffer" },
-- 				},
-- 			})
-- 		end,
-- 	},
-- }
