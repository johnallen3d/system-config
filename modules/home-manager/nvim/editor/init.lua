vim.g.mapleader = ","
vim.g.maplocalleader = ","

vim.opt.clipboard = "unnamedplus"
vim.opt.expandtab = true
vim.opt.shiftwidth = 2
vim.opt.tabstop = 2
vim.opt.termguicolors = true
vim.opt.fillchars:append({ eob = " " })

-- Pi 0.83 writes prompt.md inside pi-editor-* directories; pibuf 1.1.0 only
-- matches its older filename. Match both forms after macOS resolves /var to /private/var.
vim.api.nvim_create_autocmd({ "BufNewFile", "BufReadPost" }, {
  pattern = {
    "*/pi-editor-*.pi.md",
    "*/pi-extension-editor-*.md",
    "*/pi-editor-*/prompt.md",
  },
  callback = function(args)
    vim.bo[args.buf].filetype = "pi"
    vim.schedule(function()
      local win = vim.fn.bufwinid(args.buf)
      if win ~= -1 then
        vim.api.nvim_win_call(win, function()
          vim.cmd("keepjumps normal! G")
        end)
        vim.cmd("startinsert!")
      end
    end)
  end,
})

local theme = require("theme.managed")

vim.pack.add({
  { src = "https://github.com/folke/snacks.nvim" },
  { src = "https://github.com/S1M0N38/pibuf.nvim", version = "v1.1.0" },
  { src = "https://github.com/Saghen/blink.cmp", version = "v1.10.2", load = true },
  { src = "https://github.com/Kaiser-Yang/blink-cmp-dictionary" },
  { src = "https://github.com/moyiz/blink-emoji.nvim" },
  { src = "https://github.com/ribru17/blink-cmp-spell" },
  { src = "https://github.com/yousefhadder/markdown-plus.nvim" },
  { src = theme.plugin.src },
}, { confirm = false })

require("blink.cmp").setup({
  keymap = {
    preset = "default",
    ["<C-f>"] = { "select_and_accept" },
  },
  appearance = {
    use_nvim_cmp_as_default = false,
    nerd_font_variant = "mono",
  },
  sources = {
    default = { "dictionary", "emoji", "spell", "buffer", "path" },
    providers = {
      dictionary = {
        module = "blink-cmp-dictionary",
        name = "dictionary",
        min_keyword_length = 2,
        opts = {
          dictionary_files = { "/usr/share/dict/words" },
          force_fallback = false,
        },
      },
      emoji = {
        module = "blink-emoji",
        name = "emoji",
      },
      spell = {
        module = "blink-cmp-spell",
        name = "spell",
      },
    },
  },
  completion = {
    trigger = {
      show_on_trigger_character = true,
      show_on_keyword = true,
      prefetch_on_insert = true,
    },
    menu = {
      border = "rounded",
    },
    documentation = {
      auto_show = true,
      window = {
        border = "rounded",
      },
    },
    ghost_text = {
      enabled = true,
    },
  },
})

require("markdown-plus").setup({ filetypes = { "markdown", "pi" } })
require("pibuf").setup({ picker = "snacks" })

vim.api.nvim_create_autocmd("FileType", {
  pattern = "pi",
  callback = function(args)
    vim.opt_local.conceallevel = 1
    vim.opt_local.spell = true
    vim.opt_local.spellfile = vim.fn.expand("~/.config/nvim/spell/en.utf-8.add")
    vim.opt_local.wrap = true

    pcall(vim.keymap.del, "i", "<C-f>", { buffer = args.buf })
    pcall(vim.keymap.del, "i", "<C-s>", { buffer = args.buf })
  end,
})

require("snacks").setup({ picker = {} })
require(theme.plugin.module).setup(theme.plugin.setup)
vim.cmd.colorscheme(theme.colorscheme)
