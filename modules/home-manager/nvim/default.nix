{
  lib,
  pkgs,
  ...
}: {
  programs.neovim = {
    enable = true;
    withNodeJs = false;
    withRuby = false;
    viAlias = true;
    vimAlias = true;
    vimdiffAlias = true;

    # home.sessionVariables.EDITOR = "nvim";

    extraPackages = with pkgs; [
      # LazyVim
      lua-language-server
      stylua

      # Telescope
      ripgrep

      # LSP
      # codelldb ??? fails on M1 vscode-extensions.vadimcn.vscode-lldb
      # debugpy
      # docker-compose-language-service
      # dockerfile-language-server
      # hadolint
      # js-debug-adapter
      # json-lsp ???
      markdownlint-cli
      marksman
      nil # nix lsp
      # pyright
      # ruff-lsp
      rust-analyzer
      shfmt
      # slint-lsp
      # solargraph
      taplo
      # terraform-ls
      # typescript-language-server
      yaml-language-server
    ];

    plugins = with pkgs.vimPlugins; [
      lazy-nvim
    ];

    extraLuaConfig = let
      plugins = with pkgs.vimPlugins; [
        # LazyVim
        LazyVim

        bufferline-nvim
        cmp-buffer
        cmp-cmdline
        cmp-cmdline-history
        cmp-emoji
        cmp-nvim-lsp
        cmp-path
        cmp-tabby
        cmp_luasnip
        conform-nvim
        dashboard-nvim
        dressing-nvim
        flash-nvim
        friendly-snippets
        gitsigns-nvim
        indent-blankline-nvim
        lualine-nvim
        neo-tree-nvim
        neoconf-nvim
        neodev-nvim
        noice-nvim
        nui-nvim
        nvim-cmp
        nvim-lint
        nvim-lspconfig
        nvim-notify
        nvim-spectre
        nvim-treesitter
        nvim-treesitter-context
        nvim-treesitter-textobjects
        nvim-ts-autotag
        nvim-ts-context-commentstring
        nvim-web-devicons
        persistence-nvim
        plenary-nvim
        tabby-nvim
        telescope-fzf-native-nvim
        telescope-nvim
        todo-comments-nvim
        tokyonight-nvim
        trouble-nvim
        vim-illuminate
        vim-startuptime
        which-key-nvim
        {
          name = "LuaSnip";
          path = luasnip;
        }
        {
          name = "catppuccin";
          path = catppuccin-nvim;
        }
        {
          name = "mini.ai";
          path = mini-nvim;
        }
        {
          name = "mini.bufremove";
          path = mini-nvim;
        }
        {
          name = "mini.comment";
          path = mini-nvim;
        }
        {
          name = "mini.indentscope";
          path = mini-nvim;
        }
        {
          name = "mini.pairs";
          path = mini-nvim;
        }
        {
          name = "mini.surround";
          path = mini-nvim;
        }
      ];
      mkEntryFromDrv = drv:
        if lib.isDerivation drv
        then {
          name = "${lib.getName drv}";
          path = drv;
        }
        else drv;
      lazyPath = pkgs.linkFarm "lazy-plugins" (builtins.map mkEntryFromDrv plugins);
    in ''
      require("lazy").setup({
        defaults = {
          lazy = true,
        },
        dev = {
          -- reuse files from pkgs.vimPlugins.*
          path = "${lazyPath}",
          patterns = { "." },
          -- fallback to download
          fallback = true,
        },
        spec = {
          { "LazyVim/LazyVim", import = "lazyvim.plugins" },
          -- The following configs are needed for fixing lazyvim on nix
          -- force enable telescope-fzf-native.nvim
          { "nvim-telescope/telescope-fzf-native.nvim", enabled = true },
          -- disable mason.nvim, use programs.neovim.extraPackages
          { "williamboman/mason-lspconfig.nvim", enabled = false },
          { "williamboman/mason.nvim", enabled = false },
          -- import/override with your plugins
          { import = "plugins" },
          -- treesitter handled by xdg.configFile."nvim/parser", put this line at the end of spec to clear ensure_installed
          { "nvim-treesitter/nvim-treesitter", opts = { ensure_installed = {} } },
        },
        ui = {
          border = "single",
          size = {
            width = 0.8,
            height = 0.8,
          },
        },
        install = { colorscheme = { "tokyonight" } },
        checker = { enabled = true }, -- automatically check for plugin updates
        performance = {
          rtp = {
            -- disable some rtp plugins
            disabled_plugins = {
              "2html_plugin",
              "getscript",
              "getscriptPlugin",
              "gzip",
              "logipat",
              "matchit",
              "matchparen",
              -- "netrw",
              -- "netrwFileHandlers",
              -- "netrwPlugin",
              -- "netrwSettings",
              "remote_plugins",
              "rrhelper",
              "shada_plugin",
              "tar",
              "tarPlugin",
              "tutor_mode_plugin",
              "vimball",
              "vimballPlugin",
              "zip",
              "zipPlugin",
            },
          },
        },
      })
    '';
  };

  # https://github.com/nvim-treesitter/nvim-treesitter#i-get-query-error-invalid-node-type-at-position
  xdg.configFile."nvim/parser".source = let
    parsers = pkgs.symlinkJoin {
      name = "treesitter-parsers";
      paths =
        (pkgs.vimPlugins.nvim-treesitter.withPlugins (plugins:
          with plugins; [
            bash
            c
            fish
            lua
            markdown
            markdown_inline
            nix
            javascript
            ruby
            rust
            slint
            sql
          ]))
        .dependencies;
    };
  in "${parsers}/parser";

  # Normal LazyVim config here, see https://github.com/LazyVim/starter/tree/main/lua
  xdg.configFile."nvim/legacy.vim".source = ./legacy.vim;
  xdg.configFile."nvim/lazyvim.json".source = ./lazyvim.json;
  xdg.configFile."nvim/lua".source = ./lua;
}
