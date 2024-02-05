return {
	{
		"robitx/gp.nvim",
		enable = true,
		lazy = false,
		opts = {
			openai_api_key = os.getenv("TOGETHER_AI_API_KEY"),
			openai_api_endpoint = "https://api.together.xyz/v1/chat/completions",

			agents = {
				{
					name = "Qwen1.5-72B-Chat",
					chat = true,
					command = false,
					-- string with model name or table with model name and parameters
					model = {
						model = "Qwen/Qwen1.5-72B-Chat",
						temperature = 1.1,
						top_p = 1,
					},
					-- system prompt (use this to specify the persona/role of the AI)
					system_prompt = "You are a general AI assistant.\n\n"
						.. "The user provided the additional info about how they would like you to respond:\n\n"
						.. "- If you're unsure don't guess and say you don't know instead.\n"
						.. "- Ask question if you need clarification to provide better answer.\n"
						.. "- Think deeply and carefully from first principles step by step.\n"
						.. "- Zoom out first to see the big picture and then zoom in to details.\n"
						.. "- Use Socratic method to improve your thinking and coding skills.\n"
						.. "- Don't elide any code from your output if the answer requires coding.\n"
						.. "- Take a deep breath; You've got this!\n",
				},
				{
					name = "CodeLlama-70b-Chat",
					chat = true,
					command = false,
					-- string with model name or table with model name and parameters
					model = {
						model = "codellama/CodeLlama-70b-Instruct-hf",
						temperature = 1.1,
						top_p = 1,
					},
					-- system prompt (use this to specify the persona/role of the AI)
					system_prompt = "You are a general AI assistant.\n\n"
						.. "The user provided the additional info about how they would like you to respond:\n\n"
						.. "- If you're unsure don't guess and say you don't know instead.\n"
						.. "- Ask question if you need clarification to provide better answer.\n"
						.. "- Think deeply and carefully from first principles step by step.\n"
						.. "- Zoom out first to see the big picture and then zoom in to details.\n"
						.. "- Use Socratic method to improve your thinking and coding skills.\n"
						.. "- Don't elide any code from your output if the answer requires coding.\n"
						.. "- Take a deep breath; You've got this!\n",
				},
				{
					name = "CodeLlama-70b-Command",
					chat = false,
					command = true,
					-- string with model name or table with model name and parameters
					model = {
						model = "codellama/CodeLlama-70b-Instruct-hf",
						temperature = 0.8,
						top_p = 1,
					},
					-- system prompt (use this to specify the persona/role of the AI)
					system_prompt = "You are an AI working as a code editor.\n\n"
						.. "Please AVOID COMMENTARY OUTSIDE OF THE SNIPPET RESPONSE.\n"
						.. "START AND END YOUR ANSWER WITH:\n\n```",
				},
				{ name = "ChatGPT4" },
				{ name = "ChatGPT3-5" },
				{ name = "CodeGPT4" },
				{ name = "CodeGPT3-5" },
			},
		},
	},
}
