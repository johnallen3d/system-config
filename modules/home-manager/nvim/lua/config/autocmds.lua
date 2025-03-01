-- Autocmds are automatically loaded on the VeryLazy event
-- Default autocmds that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua

vim.api.nvim_create_augroup("AutoSave", { clear = true })

vim.api.nvim_create_autocmd("FocusLost", {
	pattern = "*",
	command = ":silent! wall",
	group = "AutoSave",
})

if vim.fn.has("mac") == 1 then
	vim.api.nvim_create_autocmd("FileType", {
		pattern = "markdown",
		callback = function()
			vim.api.nvim_buf_set_keymap(
				0,
				"n",
				"<Leader>m",
				'<cmd>silent !open -a Marked\\ 2.app "%:p"<CR>',
				{ noremap = true }
			)
		end,
	})
end
