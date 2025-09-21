local on_attach = require("config.lsp").on_attach

return {
  cmd = { "kcl-language-server" },
  filetypes = { "kcl" },
  on_attach = on_attach,
  root_markers = { "kcl.mod", ".git" },
}
