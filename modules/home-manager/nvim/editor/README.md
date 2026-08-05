# nvim-editor

Small Neovim profile for `$EDITOR` and `$VISUAL`, isolated from the full `nvim` configuration with `NVIM_APPNAME=nvim-editor`.

## Setup

Home Manager installs the `nvim-editor` wrapper and links this directory to `~/.config/nvim-editor`. The shared environment sets `EDITOR` and `VISUAL` to `nvim-editor`.

Run it directly with:

```sh
nvim-editor
```

Plugins install through Neovim's built-in `vim.pack` on first launch.

## Plugins

- `markdown-plus.nvim` — Markdown editing
- `snacks.nvim` — picker backend
- `pibuf.nvim` — Pi external-editor prompt helpers
- managed theme plugin — current shared theme

## Pi prompt editing

In Pi, press `Ctrl-G` to edit a prompt. `pibuf.nvim` recognizes the buffer and provides these buffer-local keybindings:

| Key | Action |
| --- | --- |
| `Ctrl-F` | Pick a project file; insert an `@path` mention |
| `Ctrl-S` | Pick an installed Pi skill; insert `/skill:name` |

Use `:wq` or `ZZ` to send the edited prompt. Use `:cq` to cancel and keep the original prompt. Run `:checkhealth pibuf` to diagnose plugin setup.
