local on_attach = require("config.lsp").on_attach

-- JSON Language Server (vscode-json-languageserver) configuration for
-- Neovim's built-in LSP. This file follows the project's existing pattern
-- (see lua_ls.lua) and intentionally does NOT use nvim-lspconfig or null-ls.
--
-- Installation:
--  - npm i -g vscode-langservers-extracted
--  - or install via your preferred package manager / mason if available
--
local ok, schemastore = pcall(require, "schemastore")

local settings = {
  json = {
    format = { enable = true },
    validate = { enable = true },
    schemas = {},
  },
}

if ok and schemastore and schemastore.json and schemastore.json.schemas then
  settings.json.schemas = schemastore.json.schemas()
end

return {
  cmd = { "vscode-json-language-server", "--stdio" },
  filetypes = { "json", "jsonc" },
  on_attach = on_attach,
  root_markers = { ".git", "package.json", "tsconfig.json", ".eslintrc.json" },
  settings = settings,
}
