vim.pack.add(
  { "https://github.com/bullets-vim/bullets.vim" },
  { confirm = false }
)

vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function()
    vim.g.bullets_delete_last_bullet_if_empty = 1
    vim.g.bullets_enabled_file_types = {
      "markdown",
      "gitcommit",
    }
  end,
})
