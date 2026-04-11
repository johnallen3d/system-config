vim.filetype.add({
  extension = {
    sq = "sql",
  },
  pattern = {
    [".*%.envrc"] = "direnv",
  },
})


vim.bo.commentstring = "# %s"
