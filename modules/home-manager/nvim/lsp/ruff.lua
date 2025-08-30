local on_attach = require("config.lsp").on_attach

return {
  cmd = { "ruff", "server" },
  filetypes = { "python" },
  on_attach = on_attach,
  root_markers = {
    ".git",
    ".ruff.toml",
    "pyproject.toml",
    "requirements.txt",
    "ruff.toml",
    "setup.cfg",
    "setup.py",
  },
  settings = {},
}
