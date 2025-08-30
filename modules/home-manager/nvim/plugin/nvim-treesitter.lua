vim.pack.add({
  {
    src = "https://github.com/nvim-treesitter/nvim-treesitter",
    version = "main",
  },
})

local ensure_installed = {
  "bash",
  "fish",
  "git_config",
  "gitcommit",
  "git_rebase",
  "gitignore",
  "gitattributes",
  "json",
  "jsonc",
  "just",
  "kcl",
  "lua",
  "markdown",
  "markdown_inline",
  "ninja",
  "nix",
  "python",
  "regex",
  "query",
  "ron",
  "rst",
  "rust",
  "vim",
  "vimdoc",
  "yaml",
}

local ts = require("nvim-treesitter")

ts.install(ensure_installed)

ts.setup({
  ensure_installed = ensure_installed,
  auto_install = true,
  highlight = {
    enable = true,
    additional_vim_regex_highlighting = false,
  },
  indent = {
    enable = true,
  },
})

-- Add :TSInstallMissing command to install missing ensure_installed parsers
vim.api.nvim_create_user_command("TSInstallMissing", function()
  local missing = {}
  local parser_dir = vim.fn.stdpath("data") .. "/site/parser/"
  for _, lang in ipairs(ensure_installed) do
    local parser_path = parser_dir .. lang .. ".so"
    if vim.fn.filereadable(parser_path) == 0 then
      table.insert(missing, lang)
    end
  end
  if #missing == 0 then
    vim.notify(
      "All ensure_installed parsers are already installed!",
      vim.log.levels.INFO
    )
    return
  end
  for _, lang in ipairs(missing) do
    vim.cmd("TSInstall " .. lang)
  end
end, { desc = "Install missing nvim-treesitter parsers from ensure_installed" })

local augroup = vim.api.nvim_create_augroup("treesitter", { clear = true })

-- update treesitter parsers/queries with plugin updates
vim.api.nvim_create_autocmd("PackChanged", {
  group = augroup,
  callback = function(args)
    local spec = args.data.spec
    if
      spec
      and spec.name == "nvim-treesitter"
      and args.data.kind == "update"
    then
      vim.schedule(function()
        ts.update()
      end)
    end
  end,
})
-- enable treesitter highlighting and indents
vim.api.nvim_create_autocmd("FileType", {
  group = augroup,
  callback = function(args)
    local filetype = args.match
    local lang = vim.treesitter.language.get_lang(filetype)
    if lang and vim.treesitter.language.add(lang) then
      if vim.treesitter.query.get(filetype, "indents") then
        vim.bo.indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
      end
      vim.treesitter.start()
    end
  end,
})
