-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua

--
-- standalone keymaps
--

local default_options = { noremap = true, silent = true }

-- use `-` to access netrw in current directory
-- vim.api.nvim_set_keymap("n", "-", ':Explore <bar> :sil! /<C-R>=expand("%:t")<CR><CR>', default_options)
vim.keymap.set("n", "-", "<CMD>Oil<CR>", { desc = "Open parent directory" })

-- map p (lower) to P (upper) in visual mode to not stomp on register
vim.api.nvim_set_keymap("v", "p", "P", default_options)
vim.api.nvim_set_keymap("v", "P", "p", default_options)

-- Ctrl+A to "select all" in current buffer
vim.api.nvim_set_keymap("n", "<C-A>", "ggVG", default_options)

---
-- which-key
--
local wk = require("which-key")

vim.o.timeoutlen = 300

wk.setup({
	show_keys = false,
	show_help = false,
	triggers = "auto",
	plugins = { spelling = true },
	key_labels = { ["<leader>"] = "," },
})

wk.add({
	{
		{ "<leader>w", group = "windows" },
		{ "<leader>w=", "<C-W>=", desc = "balance-window" },
		{ "<leader>wH", "<C-W>5<", desc = "expand-window-left" },
		{ "<leader>wJ", ":resize +5<CR>", desc = "expand-window-below" },
		{ "<leader>wK", ":resize -5<CR>", desc = "expand-window-up" },
		{ "<leader>wL", "<C-W>5>", desc = "expand-window-right" },
		{
			"<leader>ws",
			":split <bar> :Oil<CR>",
			desc = "split window horizontal",
		},
		{
			"<leader>wv",
			":vsplit <bar> :Oil<CR>",
			desc = "split window vertical",
		},
		{ "<leader>z", "mz[s1z=e`z", desc = "correct last typo" },
	},
})
