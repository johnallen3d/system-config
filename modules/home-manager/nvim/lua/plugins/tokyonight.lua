vim.pack.add(
  { "https://github.com/folke/tokyonight.nvim" },
  { confirm = false }
)

require("tokyonight").setup({
  style = "moon",
})

vim.cmd.colorscheme("tokyonight-moon")
