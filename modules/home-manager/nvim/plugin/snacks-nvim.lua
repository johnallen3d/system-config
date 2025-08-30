vim.pack.add({ "https://github.com/folke/snacks.nvim" })

require("snacks").setup({
  indent = {
    chunk = {
      enabled = true,
    },
  },

  picker = {
    layout = "vscode",

    -- play nice with oil.nvim
    -- https://github.com/folke/snacks.nvim/issues/1814#issuecomment-2865194886
    main = {
      file = false,
      current = true,
    },

    sources = {
      files = {
        hidden = true,
      },
      grep = {
        hidden = true,
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
