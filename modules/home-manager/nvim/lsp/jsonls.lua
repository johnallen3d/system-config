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
  root_markers = { ".git", "package.json", "tsconfig.json", ".eslintrc.json" },
  settings = settings,
}
