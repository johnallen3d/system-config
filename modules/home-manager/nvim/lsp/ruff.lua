return {
  cmd = { "ruff", "server" },
  filetypes = { "python" },
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
