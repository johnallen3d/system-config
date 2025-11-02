vim.pack.add({ "https://github.com/folke/flash.nvim" }, { confirm = false })

require("flash").setup({
  modes = {
    search = {
      enabled = true,
    },
  },
})
