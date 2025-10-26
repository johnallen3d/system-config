vim.api.nvim_create_autocmd({ "FocusGained", "TermClose", "TermLeave" }, {
  desc = "Check if we need to reload the file when it changed",
  group = vim.api.nvim_create_augroup("auto-load", { clear = true }),
  callback = function()
    if vim.o.buftype ~= "nofile" then
      vim.cmd("checktime")
    end
  end,
})
vim.api.nvim_create_autocmd("FocusLost", {
  desc = "AutoSave: Write all buffers when Neovim loses focus",
  group = vim.api.nvim_create_augroup("auto-save", { clear = true }),
  pattern = "*",
  command = ":silent! wall",
})

vim.api.nvim_create_autocmd("TextYankPost", {
  desc = "Highlight when yanking (copying) text",
  group = vim.api.nvim_create_augroup("highlight-yank", { clear = true }),
  callback = function()
    vim.highlight.on_yank()
  end,
})

vim.api.nvim_create_autocmd({ "VimResized" }, {
  desc = "resize splits if window got resized",
  group = vim.api.nvim_create_augroup("resize-splits", { clear = true }),
  callback = function()
    local current_tab = vim.fn.tabpagenr()
    vim.cmd("tabdo wincmd =")
    vim.cmd("tabnext " .. current_tab)
  end,
})

vim.api.nvim_create_autocmd("FileType", {
  desc = "Automatically start Tree-sitter highlighting for all filetypes",
  group = vim.api.nvim_create_augroup("start-treesitter", { clear = true }),
  pattern = "*",
  callback = function()
    pcall(vim.treesitter.start)
  end,
})
