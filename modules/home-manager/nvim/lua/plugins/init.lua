return {
	{
		"folke/tokyonight.nvim",
		lazy = false,
		priority = 1000,
		opts = {},
		config = function()
			require("tokyonight").setup({
				style = "moon",
				hide_inactive_statusline = true,
				lualine_bold = true,
				styles = {
					keywords = { bold = true },
				},
				on_highlights = function(hl, c)
					hl.CmpGhostText = {
						bg = c.black,
						fg = c.green1,
						italic = true,
						bold = true,
					}
				end,
			})
		end,
	},

	{
		"folke/snacks.nvim",
		opts = {
			scroll = { enabled = false },
		},
	},

	{
		"williamboman/mason.nvim",
		opts = {
			ensure_installed = {
				"kcl",
			},
		},
	},

	{
		"folke/noice.nvim",
		opts = {
			presets = {
				lsp_doc_border = true,
			},
		},
	},

	{
		"folke/flash.nvim",
		opts = {
			modes = {
				search = {
					enabled = true,
				},
			},
		},
	},

	{ "NoahTheDuke/vim-just", ft = "just" },
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

	{
		"norcalli/nvim-colorizer.lua",
		cmd = "ColorizerAttachToBuffer",
	},

	{
		"mfussenegger/nvim-lint",
		opts = {
			linters = {
				["markdownlint-cli2"] = {
					-- args = { "--disable", "MD013", "--disable", "MD041", "--" },
					args = { "--config", "~/.config/markdownlint/config.yml" },
				},
			},
		},
	},

	{
		"dkarter/bullets.vim",
		ft = "markdown",
		lazy = true,
	},

	{
		"stevearc/oil.nvim",
		event = "VeryLazy",
		config = true,
		dependencies = { "nvim-tree/nvim-web-devicons" },
		opts = {
			keymaps = {
				-- this was overriding dfault mapping (split navigation)
				["<C-h>"] = { "<C-w>h" },
				["<C-l>"] = { "<C-w>l" },
			},
			view_options = {
				show_hidden = true,
			},
		},
	},

	-- TODO: `<C-F>` mapping is overriding with my blink.cmp keypmap
	-- 	{ "ryvnf/readline.vim", event = "CmdlineEnter" },

	{ "direnv/direnv.vim" },

	{
		"echasnovski/mini.comment",
		opts = { options = { ignore_blank_line = true } },
	},

	-- {
	-- 	"nvim-lualine/lualine.nvim",
	-- 	enable = false,
	-- 	event = "VeryLazy",
	-- 	opts = {
	-- 		sections = {
	-- 			lualine_a = {},
	-- 			lualine_b = {},
	-- 			lualine_c = { { "filename", path = 1 } },
	-- 			lualine_x = {
	-- 				{ "location", padding = { left = 0, right = 1 } },
	-- 			},
	-- 			lualine_y = {},
	-- 			lualine_z = {},
	-- 		},
	-- 	},
	-- },

	{
		"neovim/nvim-lspconfig",
		opts = {
			inlay_hints = { enabled = false },
			servers = {
				slint_lsp = {
					root_dir = require("lspconfig.util").root_pattern(
						"Cargo.toml"
					),
				},
				nil_ls = {},
			},
			-- add any global capabilities here
			capabilities = {
				textDocument = {
					completion = {
						completionItem = {
							snippetSupport = false,
						},
					},
				},
			},
		},
	},

	{
		"kcl-lang/kcl.nvim",
		dependencies = "neovim/nvim-lspconfig",
		init = function()
			require("lspconfig").kcl.setup({})
		end,
	},
}
