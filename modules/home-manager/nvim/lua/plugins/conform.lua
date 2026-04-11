vim.pack.add(
  { "https://github.com/stevearc/conform.nvim" },
  { confirm = false }
)

local conform = require("conform")

local jarify_repo = vim.env.JARIFY_REPO or "/Users/john.allen/dev/src/playground/jarify"
local uv_bin = "/etc/profiles/per-user/john.allen/bin/uv"

local function sql_tool_cwd(dirname)
  local root = vim.fs.find({ "jarify.toml", ".git" }, { upward = true, path = dirname })[1]
  return root and vim.fs.dirname(root) or dirname
end

conform.setup({
  formatters = {
    jarify = {
      command = uv_bin,
      args = {
        "run",
        "--project",
        jarify_repo,
        "jarify",
        "fmt",
        "--stdin-filename",
        "$FILENAME",
        "-",
      },
      cwd = function(_, ctx)
        return sql_tool_cwd(ctx.dirname)
      end,
      stdin = true,
    },
  },
  formatters_by_ft = {
    ["*"] = { "trim_whitespace" },
    javascript = { "biome" },
    json = { "prettier" },
    kcl = { "kcl" },
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
    sql = { "jarify" },
    typescript = { "biome" },
    yaml = { "yamlfmt" },
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
