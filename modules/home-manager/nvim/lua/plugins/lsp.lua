vim.diagnostic.config({
	virtual_text = {
		enabled = true,
		severity = {
			max = vim.diagnostic.severity.WARN,
		},
	},
	virtual_lines = {
		enabled = false,
	},
})

return {
	{
		"neovim/nvim-lspconfig",
		init = function()
			local keys = require("lazyvim.plugins.lsp.keymaps").get()
			-- disable codelens related keymaps (not even sure what that is)
			keys[#keys + 1] = { "<leader>cc", false }
			keys[#keys + 1] = { "<leader>cC", false }
		end,

		opts = {
			diagnostics = {
				virtual_text = false,
				virtual_lines = false,
			},
			inlay_hints = { enabled = false },
			codelens = { enabled = false },
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
}
