vim.diagnostic.config({
  virtual_text = {
    enabled = true,
    severity = {
      max = vim.diagnostic.severity.WARN,
    },
  },
  virtual_lines = false,
})
