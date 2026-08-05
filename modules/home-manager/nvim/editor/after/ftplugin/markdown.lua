vim.opt_local.conceallevel = 1
vim.opt_local.spell = true
vim.opt_local.spellfile = vim.fn.expand("~/.config/nvim/spell/en.utf-8.add")
vim.opt_local.wrap = true

if vim.fn.has("mac") == 1 then
  vim.keymap.set("n", "<Leader>m", function()
    vim.system({ "md", vim.api.nvim_buf_get_name(0) })
  end, { buffer = true, desc = "Open Markdown preview" })
end
