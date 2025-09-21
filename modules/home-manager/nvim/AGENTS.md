# AGENTS.md

## Neovim 0.11+ Highlights

- **Native LSP Configuration:**
  - Use `vim.lsp.config.<server>` or `lsp/<server>.lua` for per-server config.
  - Enable servers with `vim.lsp.enable({ "server1", "server2" })`.
  - **This config does NOT use `nvim-lspconfig`.**
  - The `:LspInfo` command is NOT available; use `:checkhealth vim.lsp` for LSP diagnostics.
  - No need for `nvim-lspconfig` for most setups.
  - Example:

    ```lua
    -- lsp/clangd.lua
    return {
      cmd = { 'clangd', '--background-index' },
      root_markers = { 'compile_commands.json', 'compile_flags.txt' },
      filetypes = { 'c', 'cpp' },
    }
    -- In init.lua
    vim.lsp.enable({ "clangd" })
    ```

- **Auto-completion:**
  - Built-in LSP auto-completion can be enabled with `vim.lsp.completion.enable()`.
- **Improved Hover:**
  - Hover windows (`K`) now use tree-sitter for markdown highlighting.
  - Use `vim.o.winborder = 'rounded'` for floating window borders.
- **Diagnostics:**
  - Virtual text is now opt-in: `vim.diagnostic.config({ virtual_text = true })`
  - `current_line` option for showing diagnostics only on the current line.
  - Virtual lines: `vim.diagnostic.config({ virtual_lines = true })`
- **Tree-sitter:**
  - Highlighting, folding, and query iteration are now asynchronous for better performance.
  - Query caching improvements for large files.
- **Terminal:**
  - Programs in the terminal can change cursor shape/blink, use OSC 52/8 for clipboard/hyperlinks, and receive theme updates.
  - New mappings `[[` and `]]` jump between shell prompts in terminal buffers (if shell supports OSC 133).
- **Defaults:**
  - More default LSP and navigation mappings (see blog for full list).
- **Miscellaneous:**
  - Better emoji and grapheme cluster support in terminal and buffers.
  - New right-click context menu items for “Go to definition” and “Open in web browser” (on URLs).
  - Extmarks can now conceal entire lines (e.g., for Markdown code fences).

See also: `:h news`, `:h lsp-quickstart`, and the [Neovim 0.11 release notes](https://neovim.io/doc/user/news-0.11.html).

## Project Description

- This project is a Neovim configuration, focused on using Neovim version 0.12 or newer.
- Neovim is installed at: `~/.local/share/bob/nvim-bin/nvim` (nightly, v0.12)
- All configuration should be written in Lua (no Vimscript).

## Build/Test/Lint Commands

- No build, lint, or test commands detected in this directory.
- If you add Lua modules or configuration files, update this section with instructions for running tests, builds, or linters (e.g., stylua for formatting, luacheck for linting).

## IMPORTANT: Plugin Management

- This project **uses Neovim’s built-in package manager, `vim.pack`** (introduced in Neovim 0.12+).
- **Do NOT use third-party plugin managers** like packer, lazy.nvim, or vim-plug in this config.
- All plugin management must be done via `vim.pack` as described below.

## Neovim 0.12+ Built-in Package Manager: vim.pack

- Neovim 0.12 introduces a built-in package manager, `vim.pack`, for native plugin management in Lua.
- **API Summary and Best Practices (2025-07):**
  - Use `vim.pack.add()` to add plugins. It expects a **list** of plugin specs:
    - String: plugin repo full URL (e.g., "<https://github.com/owner/repo>")
    - Table: `{ src = <full URL>, version = <branch/tag/commit>, name = <custom-dir> }`
  - **Note:** Only full URLs are valid for plugin specs, whether as a string or as the value of `src` in a table. The shorthand "owner/repo" is NOT supported in any form.
  - **No lazy loading:** All plugins are loaded eagerly at startup.
  - After adding, manually call `.setup()` for plugins that require it.
  - Use the `PackChanged` autocmd to react to plugin install/update/delete events.
  - Update and remove plugins with `vim.pack.update()` and `vim.pack.del({ ... })`.
  - Plugins are managed under `~/.local/share/nvim/pack/` by default.
  - Example usage:

    ```lua
    vim.pack.add({
      "https://github.com/nvim-lua/plenary.nvim",
      { src = "https://github.com/nvim-treesitter/nvim-treesitter", version = 'main' },
      { src = "owner/repo" }, -- shorthand, expands to GitHub URL
    })
    -- After adding, setup plugins as needed:
    require("dracula").setup({})
    vim.cmd[[colorscheme dracula]]
    -- Update or remove plugins:
    vim.pack.update()
    vim.pack.del({ "nvim-lua/plenary.nvim" })
    ```

- For most users, this removes the need for third-party plugin managers.
- See also: [nvim-builtin-plugin-mgr blog post](https://bower.sh/nvim-builtin-plugin-mgr) for real-world usage and tips.

## Code Style Guidelines

- All configuration must be in Lua, following Neovim best practices.
- Use clear, descriptive names for files, variables, and functions.
- Prefer explicit `require` statements; avoid wildcard imports.
- When grouping multiple `require` statements (e.g., in `init.lua`), sort them alphabetically for clarity and consistency.
- Use 2 spaces for indentation (Lua/Neovim convention).
- Group related settings and plugins logically in separate files or modules.
- Use local variables where possible to avoid polluting the global namespace.
- Handle errors gracefully (e.g., with `pcall` for plugin loading).
- Add comments to explain non-obvious logic or customizations.
- Prefer snake_case for variable and function names.
- Avoid Vimscript unless absolutely necessary.
- If you add Cursor or Copilot rules, document them here.

## Updating This File

- Update this file whenever you add build scripts, tests, or code style rules.
- If you add Cursor rules (in .cursor/rules/ or .cursorrules) or Copilot rules (in .github/copilot-instructions.md), summarize them here for agentic tools.

## JSON LSP / Formatting

- This config includes a jsonls LSP config under lsp/jsonls.lua which uses the vscode-json-languageserver (json-language-features).
- Installation (one-time):
  - npm i -g vscode-langservers-extracted
  - Alternatively install via your system package manager or Mason if you use it externally.
- Formatting and linting notes:
  - jsonls provides JSON Schema-based validation and formatting. It will pick up schemas from schemastore if the optional Lua helper (schemastore.nvim) is available.
  - This repo prefers using conform (or nvim-lint) for formatting/linting workflows. You can continue to use conform to run Prettier or other formatters for JSON; jsonls' formatting can remain enabled but will be disabled per-language where you prefer conform-managed formatting.
  - For CI schema validation use ajv-cli (npm i -D ajv-cli) or similar tools.
