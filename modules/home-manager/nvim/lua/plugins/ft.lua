return {
	{
		"cameron-wags/rainbow_csv.nvim",
		ft = {
			"csv",
			"tsv",
			"csv_semicolon",
			"csv_whitespace",
			"csv_pipe",
			"rfc_csv",
			"rfc_semicolon",
		},
		cmd = {
			"RainbowDelim",
			"RainbowDelimSimple",
			"RainbowDelimQuoted",
			"RainbowMultiDelim",
		},
	},

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
	-- curl -L "https://github.com/cordx56/rustowl/releases/download/v0.1.1/install.sh" | sh
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
