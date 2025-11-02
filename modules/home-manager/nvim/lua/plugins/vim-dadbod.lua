vim.pack.add({
  "https://github.com/tpope/vim-dadbod",
  "https://github.com/kristijanhusak/vim-dadbod-ui",
}, { confirm = false })

-- DuckDB output mode picker
local duckdb_modes = {
  "ascii",
  "box",
  "column",
  "csv",
  "html",
  "json",
  "line",
  "list",
  "markdown",
  "quote",
  "table",
}

local function insert_duckdb_mode()
  vim.ui.select(
    duckdb_modes,
    { prompt = "Select DuckDB output mode:" },
    function(choice)
      if choice then
        local mode_cmd = ".mode " .. choice
        local line = vim.fn.line(".") - 1
        vim.api.nvim_buf_set_lines(0, line, line + 1, false, { mode_cmd })
      end
    end
  )
end

vim.keymap.set("n", "<leader>dm", insert_duckdb_mode, {
  desc = "Insert DuckDB .mode command",
  silent = true,
})

-- map <leader>e to execute sql query
vim.api.nvim_create_autocmd("FileType", {
  group = vim.api.nvim_create_augroup("dadbod-ui", { clear = true }),
  pattern = "sql",
  callback = function()
    -- Visual mode: run selection
    vim.keymap.set("v", "<leader>e", ":<C-u>'<,'>DB<CR>", {
      buffer = true,
      desc = "Run visually selected SQL with dadbod",
      silent = true,
    })
    -- Normal mode: run whole buffer
    vim.keymap.set("n", "<leader>e", function()
      vim.cmd("%DB")
    end, {
      buffer = true,
      desc = "Run entire buffer SQL with dadbod",
      silent = true,
    })
  end,
})
