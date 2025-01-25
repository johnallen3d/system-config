-- Autocmds are automatically loaded on the VeryLazy event
-- Default autocmds that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua

vim.api.nvim_create_augroup("AutoSave", { clear = true })

vim.api.nvim_create_autocmd("FocusLost", {
	pattern = "*",
	command = ":silent! wall",
	group = "AutoSave",
})
