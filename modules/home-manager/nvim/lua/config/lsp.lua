local M = {}

vim.lsp.enable({
  "biome",
  "kcl_ls",
  "nixd",
  "rust-analyzer",
  "lua_ls",
  "marksman",
  "ruff",
  "basedpyright",
  "sqruff",
  "jsonls",
})

--- Shared on_attach for all LSP servers.
--- Disables formatting for lua_ls (prefer stylua/conform.nvim).
---@param client table
---@param bufnr integer
function M.on_attach(client, bufnr)
  if client.name == "lua_ls" then
    client.server_capabilities.documentFormattingProvider = false
    client.server_capabilities.documentRangeFormattingProvider = false
  end

  local opts = { buffer = bufnr }

  vim.keymap.set("n", "K", vim.lsp.buf.hover, opts)
  vim.keymap.set("n", "gd", vim.lsp.buf.definition, opts)
  vim.keymap.set("n", "gr", vim.lsp.buf.references, opts)
  vim.keymap.set("n", "<leader>rn", vim.lsp.buf.rename, opts)
end

return M
