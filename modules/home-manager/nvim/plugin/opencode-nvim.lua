vim.pack.add({
  "https://github.com/NickvanDyke/opencode.nvim",
})

require("opencode").setup()

local map = vim.keymap.set

map("n", "<leader>oa", function()
  require("opencode").ask()
end, { desc = "Ask opencode" })

map("v", "<leader>oa", function()
  require("opencode").ask("@selection: ")
end, { desc = "Ask opencode about selection" })

map({ "n", "v" }, "<leader>op", function()
  require("opencode").select_prompt()
end, { desc = "Select prompt" })
