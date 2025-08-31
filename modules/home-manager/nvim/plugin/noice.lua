vim.pack.add({
  { src = "https://github.com/folke/noice.nvim" },
  { src = "https://github.com/MunifTanjim/nui.nvim" },
  { src = "https://github.com/rcarriga/nvim-notify" },
})

require("noice").setup({
  lsp = {
    override = {
      ["vim.lsp.util.convert_input_to_markdown_lines"] = true,
      ["vim.lsp.util.stylize_markdown"] = true,
    },
  },
  presets = {
    bottom_search = true,
    command_palette = true,
    long_message_to_split = true,
    inc_rename = false, -- input dialog for inc-rename.nvim
    lsp_doc_border = true,
  },
  messages = {
    view_search = false, -- hide search count messages
  },
  routes = {
    -- vim-dadbod-ui: hide notifications
    {
      filter = {
        any = {
          { event = "msg_show", find = "DB.*" },
          { event = "notify", find = "DB.*" },
        },
      },
      opts = { skip = true },
    },
  },
})
