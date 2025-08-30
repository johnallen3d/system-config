return {
  cmd = { "harper-ls", "--stdio" },
  filetypes = {
    "c",
    "cpp",
    "cs",
    "gitcommit",
    "go",
    "html",
    "java",
    "javascript",
    "lua",
    "markdown",
    "nix",
    "python",
    "ruby",
    "rust",
    "swift",
    "toml",
    "typescript",
    "typescriptreact",
    "haskell",
    "cmake",
    "typst",
    "php",
    "dart",
    "clojure",
  },
  root_markers = { ".git" },
  settings = {
    ["harper-ls"] = {
      userDictPath = vim.fn.expand("$HOME/.config/nvim/spell/en.utf-8.add"),
      linters = {
        SentenceCapitalization = false,
      },
      markdown = {
        -- [ignores this part]()
        -- [[ also ignores my marksman links ]]
        IgnoreLinkTitle = true,
      },
    },
  },
}
