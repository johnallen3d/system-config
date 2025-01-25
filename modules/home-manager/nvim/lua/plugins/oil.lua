return {
	"stevearc/oil.nvim",
	event = "VeryLazy",
	config = true,
	dependencies = { "echasnovski/mini.icons" },
	opts = {
		keymaps = {
			-- this was overriding dfault mapping (split navigation)
			["<C-h>"] = { "<C-w>h" },
			["<C-l>"] = { "<C-w>l" },
		},
		view_options = {
			show_hidden = true,
			is_always_hidden = function(name, _)
				return name == ".."
			end,
		},
	},
}
