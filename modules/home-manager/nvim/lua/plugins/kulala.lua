vim.pack.add(
  { "https://github.com/mistweaverco/kulala.nvim" },
  { confirm = false }
)

vim.api.nvim_create_autocmd("FileType", {
  pattern = { "http", "rest" },
  callback = function()
    if not vim.g._kulala_loaded then
      require("kulala").setup({
        global_keymaps = true,
      })
      vim.g._kulala_loaded = true
    end
  end,
})
