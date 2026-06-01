local M = {}

local function set_terminal_colors(palette)
  vim.g.terminal_color_0 = palette.black
  vim.g.terminal_color_1 = palette.red
  vim.g.terminal_color_2 = palette.green
  vim.g.terminal_color_3 = palette.yellow
  vim.g.terminal_color_4 = palette.blue
  vim.g.terminal_color_5 = palette.magenta
  vim.g.terminal_color_6 = palette.cyan
  vim.g.terminal_color_7 = palette.fg
  vim.g.terminal_color_8 = palette.comment
  vim.g.terminal_color_9 = palette.red
  vim.g.terminal_color_10 = palette.green
  vim.g.terminal_color_11 = palette.yellow
  vim.g.terminal_color_12 = palette.blue
  vim.g.terminal_color_13 = palette.magenta
  vim.g.terminal_color_14 = palette.cyanBright
  vim.g.terminal_color_15 = palette.text
end

function M.apply()
  local data = require("theme.palette")
  local highlights = require("theme.highlights").build(data)

  vim.o.termguicolors = true

  vim.cmd("highlight clear")

  if vim.fn.exists("syntax_on") == 1 then
    vim.cmd("syntax reset")
  end

  vim.g.colors_name = data.name
  set_terminal_colors(data.palette)

  for group, spec in pairs(highlights) do
    vim.api.nvim_set_hl(0, group, spec)
  end
end

return M
