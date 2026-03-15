vim.opt_local.wrap = true
vim.opt_local.spell = true

if vim.fn.has("mac") == 1 then
  vim.keymap.set("n", "<Leader>m", function()
    vim.cmd('silent !md "' .. vim.fn.expand("%:p") .. '"')
  end, { buffer = true, desc = "Open md preview" })
end

vim.opt_local.conceallevel = 1
