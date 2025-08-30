local map = vim.keymap.set

-- set leader key
---@diagnostic disable-next-line: inject-field
vim.g.mapleader = ","

-- merge default options with description and extras
local function opts(desc, extra)
  local o = { noremap = true, silent = true, desc = desc }
  if extra then
    for k, v in pairs(extra) do
      o[k] = v
    end
  end
  return o
end

-- better up/down
map(
  { "n", "x" },
  "j",
  "v:count == 0 ? 'gj' : 'j'",
  opts("Down", { expr = true })
)
map(
  { "n", "x" },
  "<Down>",
  "v:count == 0 ? 'gj' : 'j'",
  opts("Down", { expr = true })
)
map({ "n", "x" }, "k", "v:count == 0 ? 'gk' : 'k'", opts("Up", { expr = true }))
map(
  { "n", "x" },
  "<Up>",
  "v:count == 0 ? 'gk' : 'k'",
  opts("Up", { expr = true })
)

-- map p (lower) to P (upper) in visual mode to not stomp on register
map("v", "p", "P", opts("Paste without overwriting register"))
map("v", "P", "p", opts("Overwrite with register on paste"))

-- Ctrl+A to "select all" in current buffer
map("n", "<C-A>", "ggVG", opts("Select all in buffer"))

-- Use Ctrl-h/j/k/l to navigate between splits
map("n", "<C-h>", "<C-w>h", opts("Go to left split"))
map("n", "<C-j>", "<C-w>j", opts("Go to below split"))
map("n", "<C-k>", "<C-w>k", opts("Go to above split"))
map("n", "<C-l>", "<C-w>l", opts("Go to right split"))

-- Re-select visual selection after indent/outdent
map("v", ">", ">gv", opts("Indent and reselect"))
map("v", "<", "<gv", opts("Outdent and reselect"))

-- disable "Q" (ex mode)
map("n", "Q", "<nop>", opts("Go to right split"))

-- Noice
map("n", "<leader>nd", ":Noice dismiss<cr>", opts("Dismiss Noice pop-up"))

-- show diagnostics on current line
map(
  "n",
  "<leader>cd",
  vim.diagnostic.open_float,
  opts("Line Diagnostics", { noremap = nil })
)

-- copy diagnostic message to clipboard
vim.keymap.set("n", "<leader>cc", function()
  local line = vim.api.nvim_win_get_cursor(0)[1] - 1
  ---@type { message: string }|nil
  local diag = vim.diagnostic.get(0, { lnum = line })[1]
  local msg = diag and diag.message
  if type(msg) == "string" then
    vim.fn.setreg("+", msg)
    vim.notify("Diagnostic copied to clipboard!", vim.log.levels.INFO)
  else
    vim.notify("No diagnostic message found on this line.", vim.log.levels.WARN)
  end
end, opts("Copy diagnostic message to clipboard", { noremap = nil }))
