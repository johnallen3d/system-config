local on_attach = require("config.lsp").on_attach

return {
  cmd = { "nixd" },
  filetypes = { "nix" },
  on_attach = on_attach,
  settings = {
    nixd = {
      formatting = {
        command = { "alejandra" },
      },
    },
  },
}
