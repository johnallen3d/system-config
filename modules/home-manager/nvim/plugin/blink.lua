vim.pack.add({
  {
    src = "https://github.com/Saghen/blink.cmp",
    version = "v1.6.0",
    load = true,
  },

  { src = "https://github.com/zbirenbaum/copilot.lua" },

  { src = "https://github.com/kristijanhusak/vim-dadbod-completion" },
  { src = "https://github.com/Kaiser-Yang/blink-cmp-git" },
  { src = "https://github.com/mikavilpas/blink-ripgrep.nvim" },
  { src = "https://github.com/ribru17/blink-cmp-spell" },
  { src = "https://github.com/moyiz/blink-emoji.nvim" },
  { src = "https://github.com/giuxtaposition/blink-cmp-copilot" },
})

-- recommended copilot setup for best support with blink
require("copilot").setup({
  suggestion = { enabled = false },
  panel = { enabled = false },
})

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
    default = {
      "buffer",
      "copilot",
      "dadbod",
      "emoji",
      "git",
      "lsp",
      "path",
      "ripgrep",
      "spell",
    },

    providers = {
      copilot = {
        name = "copilot",
        module = "blink-cmp-copilot",
        score_offset = -100,
        async = true,
      },
      dadbod = {
        name = "Dadbod",
        module = "vim_dadbod_completion.blink",
      },
      emoji = {
        module = "blink-emoji",
        name = "emoji",
      },
      git = {
        module = "blink-cmp-git",
        name = "git",
      },
      ripgrep = {
        module = "blink-ripgrep",
        name = "ripgrep",
        score_offset = -10,
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
      show_on_insert_on_trigger_character = true,
      prefetch_on_insert = true,
    },
    menu = {
      border = "rounded",
      draw = {
        treesitter = { "lsp" },
      },
    },
    documentation = {
      auto_show = true,
      auto_show_delay_ms = 0,
      window = {
        border = "rounded",
      },
    },
    ghost_text = {
      enabled = true,
    },
  },

  -- signature = {
  --   enabled = true,
  -- },

  cmdline = {
    enabled = true,
    -- use 'inherit' to inherit mappings from top level `keymap` config
    keymap = { preset = "inherit" },
    sources = { "buffer", "cmdline" },
    completion = { menu = { auto_show = true } },
  },
})
