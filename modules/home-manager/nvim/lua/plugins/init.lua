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
		"folke/noice.nvim",
		opts = {
			presets = {
				lsp_doc_border = true,
			},
		},
	},

	{
		"nvim-treesitter/nvim-treesitter",
		opts = function(_, opts)
			if type(opts.ensure_installed) == "table" then
				vim.list_extend(
					opts.ensure_installed,
					{ "nix", "slint", "sql" }
				)
			end
		end,
	},

	{ "NoahTheDuke/vim-just" },

	{
		"norcalli/nvim-colorizer.lua",
		cmd = "ColorizerAttachToBuffer",
	},

	{
		"mfussenegger/nvim-lint",
		opts = {
			linters = {
				markdownlint = {
					args = { "--disable", "MD013", "--disable", "MD041", "--" },
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
		"prichrd/netrw.nvim",
		event = "VeryLazy",
		name = "netrw",
		config = true,
	},

	{ "ryvnf/readline.vim", event = "CmdlineEnter" },

	{ "direnv/direnv.vim" },

	-- chat

	{
		"sourcegraph/sg.nvim",
		dependencies = {
			"nvim-lua/plenary.nvim",
			"nvim-telescope/telescope.nvim",
		},
		config = true,
	},

	-- {
	-- 	"jackMort/ChatGPT.nvim",
	-- 	event = "VeryLazy",
	-- 	-- cmd = "ChatGPT",
	-- 	config = function()
	-- 		require("chatgpt").setup({
	-- 			-- tired of being pompted for each launch of NVIM, set env var instead
	-- 			-- api_key_cmd = "op read op://private/ChatGPT/secret-key-nvim --no-newline",
	-- 			openai_params = {
	-- 				model = "gpt-4-1106-preview",
	-- 				max_tokens = 2000,
	-- 			},
	-- 			openai_edit_params = {
	-- 				model = "gpt-4-1106-preview",
	-- 				max_tokens = 2000,
	-- 			},
	-- 		})
	-- 	end,
	-- 	dependencies = {
	-- 		"MunifTanjim/nui.nvim",
	-- 		"nvim-lua/plenary.nvim",
	-- 		"nvim-telescope/telescope.nvim",
	-- 	},
	-- 	keys = {
	-- 		{
	-- 			"<leader>gc",
	-- 			"<cmd>ChatGPT<CR>",
	-- 			desc = "Open prompt (ChatGPT)",
	-- 		},
	-- 		{
	-- 			"<leader>ge",
	-- 			"<cmd>ChatGPTEditWithInstruction<CR>",
	-- 			desc = "Edit with instruction (ChatGPT)",
	-- 			mode = { "n", "v" },
	-- 		},
	-- 		{
	-- 			"<leader>gg",
	-- 			"<cmd>ChatGPTRun grammar_correction<CR>",
	-- 			desc = "Grammar Correction (ChatGPT)",
	-- 			mode = { "n", "v" },
	-- 		},
	-- 		{
	-- 			"<leader>gd",
	-- 			"<cmd>ChatGPTRun docstring<CR>",
	-- 			desc = "Docstring (ChatGPT)",
	-- 			mode = { "n", "v" },
	-- 		},
	-- 		{
	-- 			"<leader>gt",
	-- 			"<cmd>ChatGPTRun add_tests<CR>",
	-- 			desc = "Add Tests (ChatGPT)",
	-- 			mode = { "n", "v" },
	-- 		},
	-- 		{
	-- 			"<leader>go",
	-- 			"<cmd>ChatGPTRun optimize_code<CR>",
	-- 			desc = "Optimize Code (ChatGPT)",
	-- 			mode = { "n", "v" },
	-- 		},
	-- 		{
	-- 			"<leader>gs",
	-- 			"<cmd>ChatGPTRun summarize<CR>",
	-- 			desc = "Summarize (ChatGPT)",
	-- 			mode = { "n", "v" },
	-- 		},
	-- 		{
	-- 			"<leader>gf",
	-- 			"<cmd>ChatGPTRun fix_bugs<CR>",
	-- 			desc = "Fix Bugs (ChatGPT)",
	-- 			mode = { "n", "v" },
	-- 		},
	-- 		{
	-- 			"<leader>gx",
	-- 			"<cmd>ChatGPTRun explain_code<CR>",
	-- 			desc = "Explain Code (ChatGPT)",
	-- 			mode = { "n", "v" },
	-- 		},
	-- 		{
	-- 			"<leader>gl",
	-- 			"<cmd>ChatGPTRun code_readability_analysis<CR>",
	-- 			desc = "Code Readability Analysis (ChatGPT)",
	-- 			mode = { "n", "v" },
	-- 		},
	-- 	},
	-- },
	-- /chat

	{
		"simrat39/symbols-outline.nvim",
		cmd = "SymbolsOutline",
		keys = {
			{
				"<leader>cs",
				"<cmd>SymbolsOutline<cr>",
				desc = "Symbols Outline",
			},
		},
		opts = {
			-- add your options that should be passed to the setup() function here
			position = "right",
		},
	},

	{
		"echasnovski/mini.comment",
		opts = { options = { ignore_blank_line = true } },
	},

	{
		"nvim-lualine/lualine.nvim",
		event = "VeryLazy",
		opts = {
			sections = {
				lualine_a = {},
				lualine_b = {},
				lualine_c = { { "filename", path = 1 } },
				lualine_x = {
					{ "location", padding = { left = 0, right = 1 } },
				},
				lualine_y = {},
				lualine_z = {},
			},
		},
	},

	{
		"nvim-telescope/telescope.nvim",
		keys = {
			{ "<leader>gc", false },
		},
		opts = function(_, opts)
			local actions = require("telescope.actions")

			return vim.tbl_extend("force", opts, {
				defaults = {
					mappings = {
						i = {
							["<esc>"] = actions.close,
							["<Down>"] = actions.close,
							["<Up>"] = actions.close,
						},
						n = {
							["<esc>"] = actions.close,
							["<Down>"] = actions.close,
							["<Up>"] = actions.close,
						},
					},
				},
			})
		end,
	},

	{
		"neovim/nvim-lspconfig",
		opts = {
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
		"hrsh7th/nvim-cmp",
		dependencies = {
			"dmitmel/cmp-cmdline-history",
			"hrsh7th/cmp-buffer",
			"hrsh7th/cmp-cmdline",
			"hrsh7th/cmp-emoji",
			"sourcegraph/sg.nvim",
		},
		---@param opts cmp.ConfigSchema
		opts = function(_, opts)
			vim.api.nvim_set_hl(
				0,
				"CmpGhostText",
				{ link = "Comment", default = true, italic = true, bold = true }
			)

			local cmp = require("cmp")

			opts.sources = cmp.config.sources(vim.list_extend(opts.sources, {
				{ name = "cody", priority = 1001 },
				{ name = "emoji" },
			}))

			-- replicate LazyVim mappings in order to override desired mappings
			-- https://github.com/LazyVim/LazyVim/discussions/1433#discussioncomment-6959614
			opts.mapping = cmp.mapping.preset.insert({
				["<C-n>"] = cmp.mapping.select_next_item({
					behavior = cmp.SelectBehavior.Insert,
				}),
				["<C-p>"] = cmp.mapping.select_prev_item({
					behavior = cmp.SelectBehavior.Insert,
				}),
				["<C-f>"] = cmp.mapping.confirm({ select = true }), -- Accept currently selected item. Set `select` to `false` to only confirm explicitly selected items.
				["<C-e>"] = cmp.mapping.abort(),
				["<Down>"] = cmp.mapping.abort(),
				["<Up>"] = cmp.mapping.abort(),
			})

			opts.window = {
				completion = cmp.config.window.bordered(),
				documentation = cmp.config.window.bordered(),
			}

			cmp.setup.cmdline(":", {
				mapping = cmp.mapping.preset.cmdline({
					["<C-f>"] = {
						c = cmp.mapping.confirm({ select = true }),
					},
				}),
				sources = {
					{ name = "cmdline" },
					{ name = "cmdline_history" },
					{ name = "path" },
				},
			})

			cmp.setup.cmdline("/", {
				mapping = cmp.mapping.preset.cmdline({
					["<C-f>"] = { c = cmp.mapping.confirm({ select = true }) }, -- Accept currently selected item. Set `select` to `false` to only confirm explicitly selected items.
				}),
				sources = {
					{ name = "buffer" },
				},
			})
		end,
	},

	{
		"kndndrj/nvim-dbee",
		ft = "sql",
		dependencies = {
			"MunifTanjim/nui.nvim",
		},
		build = function()
			-- Install tries to automatically detect the install method.
			-- if it fails, try calling it with one of these parameters:
			--    "curl", "wget", "bitsadmin", "go"
			require("dbee").install()
		end,
		config = function()
			require("dbee").setup({
				sources = {
					require("dbee.sources").MemorySource:new({
						{
							id = "duck-in-memory",
							name = "duck-in-memory",
							type = "duck",
							url = "",
						},
						{
							id = "calculate-sample",
							name = "Calculate Sample",
							type = "sqlite",
							url = os.getenv("HOME")
								.. "/dev/src/playground/calculate/tmp/sample.sqlite",
						},
					}),
				},
			})
		end,
	},

	{
		"mikesmithgh/kitty-scrollback.nvim",
		enabled = true,
		lazy = true,
		cmd = { "KittyScrollbackGenerateKittens", "KittyScrollbackCheckHealth" },
		event = { "User KittyScrollbackLaunch" },
		config = function()
			require("kitty-scrollback").setup()
		end,
	},
}
