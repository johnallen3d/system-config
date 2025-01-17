return {
	"wurli/contextindent.nvim",
	-- This is the only config option; you can use it to restrict the files
	-- which this plugin will affect (see :help autocommand-pattern).
	opts = { pattern = "*" },
	dependencies = { "nvim-treesitter/nvim-treesitter" },
}

-- return {
-- 	"OXY2DEV/markview.nvim",
-- 	lazy = false, -- Recommended
-- 	-- ft = "markdown" -- If you decide to lazy-load anyway

-- 	dependencies = {
-- 		"nvim-treesitter/nvim-treesitter",
-- 		"echasnovski/mini.icons", -- or "nvim-tree/nvim-web-devicons",
-- 	},

-- 	config = function()
-- 		local presets = require("markview.presets")

-- 		require("markview").setup({
-- 			headings = presets.headings.glow,
-- 			horizontal_rules = presets.horizontal_rules.thin,
-- 			code_blocks = {
-- 				icons = "mini",
-- 				min_width = 80,
-- 			},
-- 		})
-- 	end,
-- }
