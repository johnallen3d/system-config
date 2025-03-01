-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua

-- reset leader key provided by lazyvim
vim.g.mapleader = ","
-- hide netrw banner
vim.g.netrw_banner = 0
-- spelling
vim.opt.spellfile = vim.fn.expand("$HOME/.config/nvim/spell/en.utf-8.add")
-- enable peristent undo
vim.opt.undodir = vim.fn.expand("$HOME/tmp/vim-undo-history")
-- disable swap files
vim.opt.swapfile = false
-- start with all folds open
vim.wo.foldlevel = 99
-- show a marker at 80th character
vim.opt.colorcolumn = "81"
-- disable 🐭
vim.opt.mouse = ""
-- hide sign column
vim.opt.signcolumn = "no"
-- hide the number column
vim.opt.number = false
vim.opt.relativenumber = false
-- have :s///g flag by default on
vim.opt.gdefault = true
-- disable nvim-cmp transparency
vim.opt.pumblend = 0
vim.opt.conceallevel = 1
-- show filename and line numbers in status bar
vim.opt.statusline = "%f %=%l/%L"
