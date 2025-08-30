local opt = vim.opt

-- UI/Display
opt.wrap = false -- No line wrapping by default
opt.colorcolumn = "81" -- Show a marker at 81st character
opt.signcolumn = "no" -- Hide sign column
opt.number = false -- Hide absolute line numbers
opt.relativenumber = false -- Hide relative line numbers
opt.pumblend = 0 -- Disable popup menu transparency
opt.completeopt = "menuone,noselect" -- Completion options (blink.cmp handles its own popup)

opt.winborder = "rounded" -- Use rounded window borders
opt.cursorcolumn = false -- Disable cursor column highlight

-- Statusline/Commandline
opt.statusline = "%f %=%l/%L %c" -- Show filename and line/col in statusline
opt.laststatus = 3 -- Global statusline (one at bottom)
opt.cmdheight = 0 -- hidde the status bar

-- Clipboard & Mouse
opt.clipboard = "unnamedplus" -- Use system clipboard for all yank/paste
opt.mouse = "" -- Disable mouse
opt.mousescroll = "ver:0,hor:0" -- Disable mouse wheel scrolling

-- Editing/Indentation
opt.tabstop = 2 -- Tab width = 2 spaces
opt.shiftwidth = 2 -- Indent width = 2 spaces
opt.smartindent = true -- Enable smart indent
opt.indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"

-- Search
opt.ignorecase = true -- Ignore case in search
opt.gdefault = true -- :s///g flag by default
opt.hlsearch = false -- Disable highlight search

-- Folds/Folding
opt.foldmethod = "indent"
opt.foldexpr = "v:lua.vim.treesitter.foldexpr()"
opt.foldtext = "" -- enables syntax highlighting
opt.foldlevel = 99

-- Undo/Swap/Backup
opt.undofile = true -- Enable persistent undo
opt.undodir = vim.fn.expand("$HOME/tmp/vim-undo-history") -- Set undo directory
opt.swapfile = false -- Disable swap files
opt.undolevels = 10000

-- Spelling
opt.spellfile = vim.fn.expand("$HOME/.config/nvim/spell/en.utf-8.add") -- Custom spellfile

-- Netrw
---@diagnostic disable-next-line: inject-field
vim.g.netrw_banner = 0 -- Hide netrw banner

-- Window Splits
opt.splitbelow = true -- New splits open below
opt.splitright = true -- New splits open right

-- Tree-sitter (syntax-aware features)
-- Use Tree-sitter for indentation and folding
vim.bo.indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
vim.wo.foldexpr = "v:lua.vim.treesitter.foldexpr()"

-- UI/Display
opt.fillchars = {
  foldopen = "", -- Icon for open fold
  foldclose = "", -- Icon for closed fold
  fold = " ",
  foldsep = " ",
  diff = "╱", -- Diff filler
  eob = " ", -- Hide ~ at end of buffer
}
opt.termguicolors = true -- Enable true color support
opt.sidescrolloff = 8 -- Keep 8 columns of context when scrolling horizontally
opt.list = true -- Show invisible characters (tabs, trailing spaces, etc.)

-- Editing/Indentation
opt.expandtab = true -- Use spaces instead of tabs
opt.virtualedit = "block" -- Allow cursor to move where there is no text in visual block mode

-- Statusline/Commandline
opt.wildmode = "longest:full,full" -- Command-line completion mode

-- Disable mouse wheel scrolling
opt.mousescroll = "ver:0,hor:0"
