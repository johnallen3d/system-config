vim.pack.add(
  { "https://github.com/mfussenegger/nvim-lint" },
  { confirm = false }
)

local lint = require("lint")

lint.linters_by_ft = {
  markdown = { "markdownlint-cli2" },
  python = { "ruff" },
  sql = { "sqruff" },
}

lint.linters["markdownlint-cli2"] =
  vim.tbl_deep_extend("force", require("lint.linters.markdownlint-cli2"), {
    args = {
      "--config",
      vim.fn.expand("~/.config/markdownlint/.markdownlint-cli2.jsonc"),
    },
  })

vim.api.nvim_create_autocmd({ "BufEnter", "BufWritePost", "InsertLeave" }, {
  group = vim.api.nvim_create_augroup("NvimLint", { clear = true }),
  callback = function()
    lint.try_lint()
  end,
})
