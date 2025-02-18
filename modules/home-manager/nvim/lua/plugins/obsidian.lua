return {}

-- local vault_path = os.getenv("HOME") .. "notes"

-- return {
-- 	"epwalsh/obsidian.nvim",
-- 	version = "*", -- recommended, use latest release instead of latest commit
-- 	lazy = true,
-- 	-- ft = "markdown",
-- 	-- Replace the above line with this if you only want to load obsidian.nvim for markdown files in your vault:
-- 	event = {
-- 		-- If you want to use the home shortcut '~' here you need to call 'vim.fn.expand'.
-- 		-- E.g. "BufReadPre " .. vim.fn.expand "~" .. "/my-vault/**.md"
-- 		"BufReadPre "
-- 			.. vault_path
-- 			.. "/**.md",
-- 		"BufNewFile " .. vault_path .. "/**.md",
-- 	},
-- 	dependencies = {
-- 		"nvim-lua/plenary.nvim",
-- 		"hrsh7th/nvim-cmp",
-- 		"nvim-telescope/telescope.nvim",
-- 	},

-- 	opts = {
-- 		-- in favor of [render-markdown.nvim](https://github.com/MeanderingProgrammer/render-markdown.nvim?tab=readme-ov-file#obsidiannvim)
-- 		ui = { enable = false },

-- 		workspaces = {
-- 			{
-- 				name = "default",
-- 				path = vault_path,
-- 			},
-- 		},

-- 		daily_notes = {
-- 			folder = "journal",
-- 		},

-- 		-- completion = {
-- 		-- 	prepend_note_id = false,
-- 		-- 	prepend_note_path = false,
-- 		-- 	use_path_only = true,
-- 		-- },
-- 		-- note_id_func = function(title)
-- 		-- 	return title
-- 		-- end,

-- 		sort_by = "path",

-- 		attachments = {
-- 			-- default folder to place images in via `:ObsidianPasteImg`.
-- 			img_folder = "images",
-- 		},
-- 	},

-- 	keys = {
-- 		{
-- 			"<leader>od",
-- 			"<cmd>ObsidianToday<CR>",
-- 			desc = "Today's journal entry (Obsidian)",
-- 		},
-- 		{
-- 			"<leader>oy",
-- 			"<cmd>ObsidianYesterday<CR>",
-- 			desc = "Yesterday's journal entry (Obsidian)",
-- 		},
-- 		{
-- 			"<leader>oc",
-- 			function()
-- 				return require("obsidian").util.toggle_checkbox()
-- 			end,
-- 			desc = "Toggle checkbox (Obsidian)",
-- 		},
-- 		{
-- 			"<leader>of",
-- 			"<cmd>ObsidianFollowLink<CR>",
-- 			desc = "Follow link (Obsidian) - just use `gf`",
-- 		},
-- 		{
-- 			"<leader>ob",
-- 			"<cmd>ObsidianBacklinks<CR>",
-- 			desc = "Backlinks open (Obsidian)",
-- 		},
-- 		{
-- 			"<leader>on",
-- 			"<cmd>ObsidianNew<CR>",
-- 			desc = "New note (Obsidian)",
-- 		},
-- 		{
-- 			"<leader>os",
-- 			"<cmd>ObsidianQuickSwitch<CR>",
-- 			desc = "Switch/Find note (Obsidian)",
-- 		},
-- 	},
-- }
