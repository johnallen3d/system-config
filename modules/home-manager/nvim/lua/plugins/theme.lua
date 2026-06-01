local theme = require("theme.managed")

vim.pack.add({
  {
    src = theme.plugin.src,
  },
}, { confirm = false })

require(theme.plugin.module).setup(theme.plugin.setup)
vim.cmd.colorscheme(theme.colorscheme)
