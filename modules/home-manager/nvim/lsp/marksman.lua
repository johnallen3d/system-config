local on_attach = require("config.lsp").on_attach

return {
  cmd = { "marksman", "server" },
  filetypes = { "markdown" },
  on_attach = on_attach,
  root_markers = { ".git", ".marksman.toml" },
  settings = {},
}
