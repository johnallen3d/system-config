return {
	{
		"hrsh7th/nvim-cmp",
		dependencies = {
			"dmitmel/cmp-cmdline-history",
			"hrsh7th/cmp-cmdline",
			"hrsh7th/cmp-emoji",
			{
				"nzlov/cmp-tabby",
				config = function()
					local tabby = require("cmp_tabby.config")

					tabby:setup({
						host = "http://localhost:8080",
						max_lines = 1000,
					})
				end,
			},
		},
		---@param opts cmp.ConfigSchema
		opts = function(_, opts)
			vim.api.nvim_set_hl(
				0,
				"CmpGhostText",
				{ link = "Comment", default = true, italic = true, bold = true }
			)

			local cmp = require("cmp")

			opts.sources = cmp.config.sources(vim.list_extend(opts.sources, {
				{ name = "cmp_tabby", priority = 1001 },
				{ name = "emoji" },
			}))

			-- replicate LazyVim mappings in order to override desired mappings
			-- https://github.com/LazyVim/LazyVim/discussions/1433#discussioncomment-6959614
			opts.mapping = cmp.mapping.preset.insert({
				["<C-n>"] = cmp.mapping.select_next_item({
					behavior = cmp.SelectBehavior.Insert,
				}),
				["<C-p>"] = cmp.mapping.select_prev_item({
					behavior = cmp.SelectBehavior.Insert,
				}),
				["<C-f>"] = cmp.mapping.confirm({ select = true }), -- Accept currently selected item. Set `select` to `false` to only confirm explicitly selected items.
				["<C-e>"] = cmp.mapping.abort(),
				["<Down>"] = cmp.mapping.abort(),
				["<Up>"] = cmp.mapping.abort(),
			})

			opts.window = {
				completion = cmp.config.window.bordered(),
				documentation = cmp.config.window.bordered(),
			}

			cmp.setup.cmdline(":", {
				mapping = cmp.mapping.preset.cmdline({
					["<C-f>"] = {
						c = cmp.mapping.confirm({ select = true }),
					},
				}),
				sources = {
					{ name = "cmdline" },
					{ name = "cmdline_history" },
					{ name = "path" },
				},
			})

			cmp.setup.cmdline("/", {
				mapping = cmp.mapping.preset.cmdline({
					["<C-f>"] = { c = cmp.mapping.confirm({ select = true }) }, -- Accept currently selected item. Set `select` to `false` to only confirm explicitly selected items.
				}),
				sources = {
					{ name = "buffer" },
				},
			})
		end,
	},
}
