local chat_prompt = "You are a general AI assistant.\n\n"
	.. "The user provided the additional info about how they would like you to respond:\n\n"
	.. "- If you're unsure don't guess and say you don't know instead.\n"
	.. "- Ask question if you need clarification to provide better answer.\n"
	.. "- Think deeply and carefully from first principles step by step.\n"
	.. "- Zoom out first to see the big picture and then zoom in to details.\n"
	.. "- Use Socratic method to improve your thinking and coding skills.\n"
	.. "- Don't elide any code from your output if the answer requires coding.\n"
	.. "- Keep your answers brief and suscint unless otherwise requested\n"
	.. "- Take a deep breath; You've got this!\n"

return {
	{
		"robitx/gp.nvim",
		keys = {
			{
				"<leader>gf",
				"<cmd>GpChatFinder<cr>",
				desc = "Find chat (gp.nvim)",
			},
			{
				"<leader>gn",
				"<cmd>GpChatNew<cr>",
				desc = "New chat (gp.nvim)",
			},
			{
				"<leader>gd",
				"<cmd>GpPrepend add doc comments including an # Errors section, do not exceed 80 characters, wrap types in backticks<cr>",
				mode = "v",
				desc = "Add doc comments (gp.nvim)",
			},
		},
		opts = {
			providers = {
				openai = {
					secret = os.getenv("OPENAI_API_KEY"),
				},
				anthropic = {
					endpoint = "https://api.anthropic.com/v1/messages",
					secret = os.getenv("ANTHROPIC_API_KEY"),
				},
			},
			agents = {
				{
					name = "ChatGPT3-5",
					disable = true,
				},
				{
					name = "CodeGPT4o",
					chat = true,
					command = true,
					model = { model = "gpt-4o", temperature = 0.7, top_p = 1 },
					system_prompt = chat_prompt,
				},
				{
					name = "CodeGPT-o1-mini",
					chat = true,
					command = true,
					model = { model = "o1-mini", temperature = 0.7, top_p = 1 },
					system_prompt = chat_prompt,
				},
				{
					provider = "anthropic",
					name = "ChatClaude-3-5-Sonnet",
					chat = true,
					command = false,
					model = {
						model = "claude-3-5-sonnet-20240620",
						temperature = 0.5,
						top_p = 1,
					},
					system_prompt = chat_prompt,
				},
			},
		},
	},

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
					adapter = "copilot",
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
