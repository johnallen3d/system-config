return {
	{
		"MeanderingProgrammer/render-markdown.nvim",
		ft = { "markdown", "codecompanion" },
		opts = {
			render_modes = true,
			sign = {
				enabled = false,
			},
		},
	},

	{
		"bullets-vim/bullets.vim",
		ft = { "markdown" },
		config = function()
			vim.g.bullets_delete_last_bullet_if_empty = 1
		end,
	},

	{
		"mfussenegger/nvim-lint",
		opts = {
			linters = {
				["markdownlint-cli2"] = {
					-- args = { "--disable", "MD013", "--disable", "MD041", "--" },
					args = { "--config", "~/.config/markdownlint/config.yml" },
				},
			},
		},
	},
}
