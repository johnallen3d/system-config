vim.pack.add({ "https://github.com/mrcjkb/rustaceanvim" })

local shared_on_attach = require("config.lsp").on_attach

vim.g.rustaceanvim = {
  server = {
    on_attach = function(client, bufnr)
      -- Call shared on_attach first for common keymaps and setup
      shared_on_attach(client, bufnr)

      -- Rust-specific keymaps (override global <leader>ca)
      vim.keymap.set("n", "<leader>ca", function()
        vim.cmd.RustLsp("codeAction")
      end, { desc = "Code Action", buffer = bufnr })
    end,
    default_settings = {
      -- rust-analyzer language server configuration
      ["rust-analyzer"] = {
        cargo = {
          allFeatures = true,
          loadOutDirsFromCheck = true,
          buildScripts = {
            enable = true,
          },
        },
        checkOnSave = true,
        diagnostics = {
          enable = true,
        },
        procMacro = {
          enable = true,
          ignored = {
            ["async-trait"] = { "async_trait" },
            ["napi-derive"] = { "napi" },
            ["async-recursion"] = { "async_recursion" },
          },
        },
        files = {
          excludeDirs = {
            ".direnv",
            ".git",
            ".github",
            ".gitlab",
            "bin",
            "node_modules",
            "target",
            "venv",
            ".venv",
          },
        },
      },
    },
  },
}
