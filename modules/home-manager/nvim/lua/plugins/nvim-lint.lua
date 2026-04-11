vim.pack.add(
  { "https://github.com/mfussenegger/nvim-lint" },
  { confirm = false }
)

local lint = require("lint")

local jarify_repo = vim.env.JARIFY_REPO or "/Users/john.allen/dev/src/playground/jarify"
local uv_bin = "/etc/profiles/per-user/john.allen/bin/uv"

local severity_map = {
  error = vim.diagnostic.severity.ERROR,
  warn = vim.diagnostic.severity.WARN,
}

local function json_number(value, default)
  if value == vim.NIL or value == nil then
    return default
  end

  local number = tonumber(value)
  if number == nil then
    return default
  end

  return number
end

local function sql_tool_cwd(bufnr)
  local filename = vim.api.nvim_buf_get_name(bufnr)
  if filename == "" then
    return vim.fn.getcwd()
  end

  local dirname = vim.fs.dirname(filename)
  local root = vim.fs.find({ "jarify.toml", ".git" }, { upward = true, path = dirname })[1]
  return root and vim.fs.dirname(root) or dirname
end

lint.linters_by_ft = {
  markdown = { "markdownlint-cli2" },
  python = { "ruff" },
  sql = { "jarify" },
}

lint.linters.jarify = {
  cmd = uv_bin,
  stdin = true,
  args = {
    "run",
    "--project",
    jarify_repo,
    "python",
    "-c",
    [[import json, sys
from jarify.config import load_config
from jarify.linter import lint_sql

filename = sys.argv[1] if len(sys.argv) > 1 else "<stdin>"
sql = sys.stdin.read()

try:
    config = load_config(None)
    violations = lint_sql(sql, config)
except Exception as exc:
    json.dump([
        {
            "filename": filename,
            "line": 1,
            "column": 1,
            "severity": "error",
            "rule": "jarify",
            "message": str(exc),
        }
    ], sys.stdout)
    sys.stdout.write("\n")
    raise SystemExit(2)

json.dump([
    {
        "filename": filename,
        "line": violation.line,
        "column": violation.column,
        "severity": violation.severity,
        "rule": violation.rule,
        "message": violation.message,
    }
    for violation in violations
], sys.stdout)
sys.stdout.write("\n")
raise SystemExit(1 if violations else 0)
]],
    function()
      return vim.api.nvim_buf_get_name(0)
    end,
  },
  ignore_exitcode = true,
  parser = function(output, bufnr)
    if output == nil or vim.trim(output) == "" then
      return {}
    end

    local ok, decoded = pcall(vim.json.decode, output)
    if not ok then
      return {
        {
          lnum = 0,
          col = 0,
          end_lnum = 0,
          end_col = 0,
          message = output,
          source = "jarify",
          severity = vim.diagnostic.severity.ERROR,
        },
      }
    end

    local filename = vim.fs.normalize(vim.api.nvim_buf_get_name(bufnr))
    local diagnostics = {}

    for _, item in ipairs(decoded or {}) do
      local item_filename = item.filename and item.filename ~= vim.NIL and vim.fs.normalize(item.filename) or filename
      if item_filename == filename then
        local lnum = math.max(json_number(item.line, 1) - 1, 0)
        local col = math.max(json_number(item.column, 1) - 1, 0)
        table.insert(diagnostics, {
          lnum = lnum,
          col = col,
          end_lnum = lnum,
          end_col = col,
          message = string.format("[%s] %s", item.rule or "jarify", item.message),
          code = item.rule,
          source = "jarify",
          severity = severity_map[item.severity] or vim.diagnostic.severity.WARN,
        })
      end
    end

    return diagnostics
  end,
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
  callback = function(args)
    local opts
    if vim.bo[args.buf].filetype == "sql" then
      opts = { cwd = sql_tool_cwd(args.buf) }
    end
    lint.try_lint(nil, opts)
  end,
})
