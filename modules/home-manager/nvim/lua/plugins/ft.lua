return {
	{
		"hat0uma/csvview.nvim",
		opts = {
			parser = { comments = { "#", "//" } },
			keymaps = {
				-- Text objects for selecting fields
				textobject_field_inner = { "if", mode = { "o", "x" } },
				textobject_field_outer = { "af", mode = { "o", "x" } },
				-- Excel-like navigation:
				-- Use <Tab> and <S-Tab> to move horizontally between fields.
				-- Use <Enter> and <S-Enter> to move vertically between rows and place the cursor at the end of the field.
				-- Note: In terminals, you may need to enable CSI-u mode to use <S-Tab> and <S-Enter>.
				jump_next_field_end = { "<Tab>", mode = { "n", "v" } },
				jump_prev_field_end = { "<S-Tab>", mode = { "n", "v" } },
				jump_next_row = { "<Enter>", mode = { "n", "v" } },
				jump_prev_row = { "<S-Enter>", mode = { "n", "v" } },
			},
		},
		cmd = { "CsvViewEnable", "CsvViewDisable", "CsvViewToggle" },
	},

	{ "direnv/direnv.vim" },

	{
		"bezhermoso/tree-sitter-ghostty",
		lazy = true,
		build = "make nvim_install",
		ft = "ghostty",
	},

	{ "NoahTheDuke/vim-just", ft = "just" },

	{
		"kcl-lang/kcl.nvim",
		ft = "kcl",
		dependencies = "neovim/nvim-lspconfig",
		init = function()
			require("lspconfig").kcl.setup({})
		end,
	},

	-- TODO: keep an eye out for a Nix package or brew for this
  -- curl -L "https://github.com/cordx56/rustowl/releases/latest/download/install.sh" | sh
	{
		"cordx56/rustowl",
		enabled = false,
		dependencies = { "neovim/nvim-lspconfig" },
		ft = { "rust" },
		config = function()
			local lspconfig = require("lspconfig")
			lspconfig.rustowlsp.setup({})
		end,
	},
}
