return {
	{
		"olimorris/codecompanion.nvim",
		dependencies = {
			"nvim-lua/plenary.nvim",
			"nvim-treesitter/nvim-treesitter",
		},
		opts = {
			extensions = {
				mcphub = {
					callback = "mcphub.extensions.codecompanion",
					opts = {
						make_vars = true,
						make_slash_commands = true,
						show_result_in_chat = true,
					},
				},
			},
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
	{
		"ravitemer/mcphub.nvim",
		dependencies = {
			"nvim-lua/plenary.nvim",
		},
		-- comment the following line to ensure hub will be ready at the earliest
		cmd = "MCPHub", -- lazy load by default
		-- build = "npm install -g mcp-hub@latest", -- Installs required mcp-hub npm module
		build = "bundled_build.lua",
		config = function()
			require("mcphub").setup({
				auto_approve = true,
				use_bundled_binary = true,
			})
		end,
	},
}
