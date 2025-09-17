vim.filetype.add({
  pattern = {
    [".*%.envrc"] = "direnv",
  },
})


vim.bo.commentstring = "# %s"
