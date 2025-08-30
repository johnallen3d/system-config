local on_attach = require("config.lsp").on_attach

return {
  cmd = { "sqruff", "lsp" },
  filetypes = { "sql" },
  on_attach = on_attach,
  root_markers = { ".sqruff", ".git" },
}
