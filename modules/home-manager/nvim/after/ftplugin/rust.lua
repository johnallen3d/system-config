local bufnr = vim.api.nvim_get_current_buf()
local map = function(mode, lhs, rhs, desc)
  vim.keymap.set(mode, lhs, rhs, { silent = true, buffer = bufnr, desc = desc })
end

map("n", "<leader>a", function()
  vim.cmd.RustLsp("codeAction")
end, "Rust code actions (grouped)")

map("n", "K", function()
  vim.cmd.RustLsp({ "hover", "actions" })
end, "Rust hover actions")
