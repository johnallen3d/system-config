vim.opt_local.wrap = true

if vim.fn.has("mac") == 1 then
  vim.keymap.set("n", "<Leader>m", function()
    vim.cmd('silent !open -a Marked\\ 2.app "' .. vim.fn.expand("%:p") .. '"')
  end, { buffer = true, desc = "Open Marked 2 preview" })
end

vim.opt_local.conceallevel = 1
