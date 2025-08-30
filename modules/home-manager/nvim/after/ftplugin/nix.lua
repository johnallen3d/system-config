-- Nix filetype settings
-- Disable tree-sitter indentation and use basic vim indenting

-- Basic indentation settings
vim.bo.tabstop = 2
vim.bo.shiftwidth = 2
vim.bo.expandtab = true
vim.bo.autoindent = true
vim.bo.smartindent = false

-- Disable tree-sitter indentexpr for nix files
vim.bo.indentexpr = ""
