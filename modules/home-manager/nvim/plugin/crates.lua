vim.pack.add({ "https://github.com/Saecki/crates.nvim" })

require("crates").setup({
  completion = {
    crates = {
      enabled = true,
    },
  },
  lsp = {
    enabled = true,
    actions = true,
    completion = true,
    hover = true,
  },
})
