vim.pack.add({
  { src = "https://github.com/kevinhwang91/nvim-ufo" },
  { src = "https://github.com/kevinhwang91/promise-async" },
})

require("ufo").setup({
  provider_selector = function(_bufnr, _filetype, _buftype)
    return { "lsp", "indent" }
  end,
})
