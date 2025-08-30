local on_attach = require("config.lsp").on_attach

return {
  cmd = { "kcl-language-server" },
  filetypes = { "kcl" },
  on_attach = on_attach,
  root_dir = function(fname)
    if type(fname) == "number" then
      fname = vim.api.nvim_buf_get_name(fname)
    end
    return vim.fs.dirname(
      vim.fs.find({ "kcl.mod", ".git" }, { upward = true, path = fname })[1]
    )
  end,
}
