vim.g.mapleader = ","
vim.g.maplocalleader = ","

vim.opt.clipboard = "unnamedplus"
vim.opt.expandtab = true
vim.opt.shiftwidth = 2
vim.opt.tabstop = 2
vim.opt.termguicolors = true
vim.opt.fillchars:append({ eob = " " })

local theme = require("theme.managed")

vim.pack.add({
  { src = "https://github.com/yousefhadder/markdown-plus.nvim" },
  { src = theme.plugin.src },
}, { confirm = false })

require("markdown-plus").setup()
require(theme.plugin.module).setup(theme.plugin.setup)
vim.cmd.colorscheme(theme.colorscheme)
