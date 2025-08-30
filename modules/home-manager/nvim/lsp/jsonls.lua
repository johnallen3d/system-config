local on_attach = require("config.lsp").on_attach

local settings = {
  json = {
    format = { enable = true },
    validate = { enable = true },
    schemas = {},
  },
}

return {
  cmd = { "vscode-json-language-server", "--stdio" },
  filetypes = { "json", "jsonc" },
  on_attach = on_attach,
  root_markers = { ".git", "package.json", "tsconfig.json", ".eslintrc.json" },
  settings = settings,
}
