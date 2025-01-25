return {
	{
		"folke/tokyonight.nvim",
		lazy = false,
		priority = 1000,
		opts = {
			hide_inactive_statusline = true,
			styles = {
				keywords = { bold = true },
			},
			on_highlights = function(hl, c)
				hl.BlinkCmpGhostText = {
					bg = c.black,
					fg = c.green1,
					italic = true,
					bold = true,
				}
			end,
		},
	},

	{
		"folke/noice.nvim",
		opts = {
			presets = {
				lsp_doc_border = true,
			},
		},
	},

	{
		"echasnovski/mini.comment",
		opts = { options = { ignore_blank_line = true } },
	},

	{
		"norcalli/nvim-colorizer.lua",
		cmd = "ColorizerAttachToBuffer",
	},
}
