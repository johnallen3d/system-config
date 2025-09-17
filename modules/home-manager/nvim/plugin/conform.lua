vim.pack.add({ "https://github.com/stevearc/conform.nvim" })

local conform = require("conform")

conform.setup({
  formatters_by_ft = {
    ["*"] = { "trim_whitespace" },
    javascript = { "biome" },
    json = { "prettier" },
    lua = { "stylua" },
    nix = { "alejandra" },
    markdown = { "prettier", "markdownlint-cli2" },
    ["markdown.mdx"] = { "prettier", "markdownlint-cli2" },
    python = {
      "ruff_fix",
      "ruff_format",
      "ruff_organize_imports",
    },
    rust = { "rustfmt" },
    sql = { "sqruff" },
    typescript = { "biome" },
  },
  format_on_save = {
    timeout_ms = 500,
    lsp_format = "fallback",
  },
  notify_on_error = true,
})

vim.api.nvim_create_user_command("Format", function()
  conform.format({ async = false, lsp_fallback = true })
end, { desc = "Format buffer with conform.nvim (stylua for Lua)" })

local map = vim.keymap.set

map("n", "<leader>lf", function()
  vim.cmd("Format")
end, { desc = "Format buffer with conform.nvim" })
