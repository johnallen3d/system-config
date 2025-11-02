vim.pack.add({ "https://github.com/folke/snacks.nvim" }, { confirm = false })

require("snacks").setup({
  indent = {
    chunk = {
      enabled = true,
    },
  },

  picker = {
    -- play nice with oil.nvim
    -- https://github.com/folke/snacks.nvim/issues/1814#issuecomment-2865194886
    main = {
      file = false,
      current = true,
    },

    sources = {
      files = {
        hidden = true,
        layout = "vscode",
      },
      grep = {
        hidden = true,
        layout = "vscode",
      },
    },

    win = {
      input = {
        keys = {
          ["<Esc>"] = { "close", mode = { "n", "i" } },
        },
      },
    },
  },
})

local map = vim.keymap.set

map("n", "<leader>ff", function()
  Snacks.picker.files()
end, { desc = "Find files (snacks)" })
map("n", "<leader>sg", function()
  Snacks.picker.grep({ live = true })
end, { desc = "Live grep (snacks)" })
map("n", "<leader>gi", function()
  Snacks.picker.gh_issue()
end, { desc = "GitHub Issues (open)" })
map("n", "<leader>gI", function()
  Snacks.picker.gh_issue({ state = "all" })
end, { desc = "GitHub Issues (all)" })
map("n", "<leader>gp", function()
  Snacks.picker.gh_pr()
end, { desc = "GitHub Pull Requests (open)" })
map("n", "<leader>gP", function()
  Snacks.picker.gh_pr({ state = "all" })
end, { desc = "GitHub Pull Requests (all)" })
