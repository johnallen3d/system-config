vim.pack.add({ "https://github.com/stevearc/oil.nvim" }, { confirm = false })

require("oil").setup({
  keymaps = {
    -- this was overriding dfault mapping (split navigation)
    ["<C-h>"] = { "<C-w>h" },
    ["<C-l>"] = { "<C-w>l" },
  },
  view_options = {
    show_hidden = true,
    is_always_hidden = function(name, _)
      return name == ".."
    end,
  },
})

local map = vim.keymap.set

map("n", "-", "<CMD>Oil<CR>", { desc = "Open parent directory" })
map(
  "n",
  "<leader>ws",
  ":split <bar> :Oil<CR>",
  { noremap = true, silent = true, desc = "split window horizontal (Oil)" }
)
map(
  "n",
  "<leader>wv",
  ":vsplit <bar> :Oil<CR>",
  { noremap = true, silent = true, desc = "split window vertical (Oil)" }
)
