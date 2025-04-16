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
					tools = {
						["mcp"] = {
							callback = function()
								return require(
									"mcphub.extensions.codecompanion"
								)
							end,
							description = "Call tools and resources from the MCP Servers",
						},
					},
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
		build = "npm install -g mcp-hub@latest", -- Installs required mcp-hub npm module
		-- uncomment this if you don't want mcp-hub to be available globally or can't use -g
		-- build = "bundled_build.lua",  -- Use this and set use_bundled_binary = true in opts  (see Advanced configuration)
		config = function()
			require("mcphub").setup({
				auto_approve = true,
				extensions = {
					codecompanion = {
						-- Show the mcp tool result in the chat buffer
						show_result_in_chat = true,
						-- Make chat #variables from MCP server resources
						make_vars = true,
						-- make /slash_commands from MCP server prompts
						make_slash_commands = true,
					},
				},
			})
		end,
	},
}
