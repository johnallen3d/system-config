return {
	{
		"robitx/gp.nvim",
		branch = "copilot",
		enable = true,
		lazy = false,
		opts = {
			providers = {
				openai = {
					secret = os.getenv("OPENAI_API_KEY"),
				},
				anthropic = {
					secret = os.getenv("ANTHROPIC_API_KEY"),
				},
			},
		},
		-- opts = {
		-- 	-- openai_api_key = os.getenv("TOGETHER_AI_API_KEY"),
		-- 	-- openai_api_endpoint = "https://api.together.xyz/v1/chat/completions",
		-- 	openai_api_key = os.getenv("MISTRAL_API_KEY"),
		-- 	openai_api_endpoint = "https://api.mistral.ai/v1/chat/completions",

		-- 	agents = {
		-- 		{
		-- 			name = "mistral-large-chat",
		-- 			chat = true,
		-- 			command = false,
		-- 			-- string with model name or table with model name and parameters
		-- 			model = {
		-- 				model = "mistral-large-latest",
		-- 				temperature = 0.75,
		-- 				top_p = 1,
		-- 			},
		-- 			-- system prompt (use this to specify the persona/role of the AI)
		-- 			system_prompt = "You are a helpful AI assistant.\n\n"
		-- 				.. "Below is an instruction that describes a task.\n"
		-- 				.. "Write a response that appropriately completes the request.\n"
		-- 				.. "Answer as concisely as possible.\n"
		-- 				.. "When approprite provide a bulleted list to summarize your response.\n"
		-- 				.. "Do not output your internal dialog!\n",
		-- 			-- system_prompt = "You are a general AI assistant.\n\n"
		-- 			-- 	.. "The user provided the additional info about how they would like you to respond:\n\n"
		-- 			-- 	.. "- If you're unsure don't guess and say you don't know instead.\n"
		-- 			-- 	.. "- Ask question if you need clarification to provide better answer.\n"
		-- 			-- 	.. "- Think deeply and carefully from first principles step by step.\n"
		-- 			-- 	.. "- Zoom out first to see the big picture and then zoom in to details.\n"
		-- 			-- 	.. "- Use Socratic method to improve your thinking and coding skills.\n"
		-- 			-- 	.. "- Don't elide any code from your output if the answer requires coding.\n"
		-- 			-- 	.. "- Don't think out loud, only respond when you have something useful to say to the user.\n"
		-- 			-- 	.. "- Take a deep breath; You've got this!\n",
		-- 		},
		-- 		{
		-- 			name = "mistral-large-command",
		-- 			chat = false,
		-- 			command = true,
		-- 			-- string with model name or table with model name and parameters
		-- 			model = {
		-- 				model = "mistral-large-latest",
		-- 				temperature = 0.8,
		-- 				top_p = 1,
		-- 			},
		-- 			-- system prompt (use this to specify the persona/role of the AI)
		-- 			system_prompt = "You are an AI working as a code editor.\n\n"
		-- 				.. "Please AVOID COMMENTARY OUTSIDE OF THE SNIPPET RESPONSE.\n"
		-- 				.. "START AND END YOUR ANSWER WITH:\n\n```",
		-- 		},
		-- 		{ name = "ChatGPT4" },
		-- 		{ name = "ChatGPT3-5" },
		-- 		{ name = "CodeGPT4" },
		-- 		{ name = "CodeGPT3-5" },
		-- 	},
		-- 	chat_topic_gen_model = "mistral-large-latest",
		-- 	chat_confirm_delete = false,
		-- },
	},
}
