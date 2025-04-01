return {
	{
		"olimorris/codecompanion.nvim",
		dependencies = {
			"nvim-lua/plenary.nvim",
			"nvim-treesitter/nvim-treesitter",
		},
		opts = {
			adapters = {
				copilot = function()
					return require("codecompanion.adapters").extend("copilot", {
						schema = {
							model = {
								default = "claude-3.7-sonnet",
							},
						},
					})
				end,
			},
			strategies = {
				chat = {
					adapter = os.getenv("NVIM_CODECOMPANION_CHAT_ADAPTER")
						or "copilot",
				},
				inline = {
					adapter = "copilot",
				},
			},
			display = {
				chat = {
					window = {
						opts = {
							spell = true,
						},
					},
				},
			},
		},
		keys = {
			{
				"<leader>cc",
				"<cmd>CodeCompanionChat Toggle<CR>",
				desc = "Toggle LLM Chat (CodeCompanion)",
			},
		},
	},
}
