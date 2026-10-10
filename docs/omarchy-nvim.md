# Omarchy Neovim

Tracked in [Fizzy #729](https://app.fizzy.do/6284043/cards/729).

`hosts/omarchy.nix` opts into `modules/home-manager/omarchy-nvim.nix`. It imports
exactly the Mac's `nvim` module and an editor-specific CLI package list, not the
Mac desktop or its full package suite. Neovim on Omarchy comes from locked
nixpkgs (0.12+); Mac keeps its Bob installation.

## Parity and ownership

- Same Lua configuration, eager `vim.pack` plugins, comma leader, keybindings,
  LSP setup, formatting/linting, Tree-sitter, and managed Rose Pine theme.
- `nvim` is the full editor; `nvim-editor` is the smaller Markdown/Pi editor.
  Fresh sessions select `EDITOR=VISUAL=nvim-editor`, `GIT_EDITOR=nvim`.
- Home Manager owns configuration links only. Plugin locks/checkouts, parsers,
  spelling additions, undo history, and credentials remain writable host-local
  runtime state. Never copy compiled Mac plugins/parsers to Linux.
- The small editor uses `/usr/share/dict/words` when present (Mac); otherwise it
  uses a Nix-managed SCOWL word list. This does not modify `/usr/share`.
- Omarchy receives required formatters, language servers, search/database tools,
  compiler, Tree-sitter CLI, and Wayland clipboard helpers through Nix.
  Amfaro's Python `jarify` is pinned to the Mac's 0.14.0 via a Nix-owned `uv tool
  run` wrapper; first use downloads its isolated environment. It is unrelated
  to nixpkgs' Haskell package with the same name. No credentials are needed.
- Omarchy's Hyprland, terminal, desktop theme, Bash, and other native settings
  remain untouched. Its old LazyVim hot-reload plugin is not part of this editor.

## Clipboard over SSH

Tracked in [Fizzy #737](https://app.fizzy.do/6284043/cards/737).
Both Omarchy editor profiles load a host-only clipboard plugin. With
`SSH_CONNECTION` set and neither `WAYLAND_DISPLAY` nor `DISPLAY` available,
it explicitly selects Neovim's built-in OSC 52 provider. Our shared
`clipboard=unnamedplus` setting otherwise disables automatic OSC 52 detection,
causing "clipboard: No provider" even though `wl-clipboard` is installed.
Native Wayland/X11 sessions and explicit user/GUI providers are left alone;
the Mac editor configuration is unchanged.

SSH yanks target the **client terminal's clipboard**, not Omarchy's desktop
clipboard. The terminal/UI must support forwarding OSC 52 and allow clipboard
writes; paste queries additionally require clipboard-read support/permission.
Do not synthesize a desktop display environment in an SSH session.
Reopen the editor after activation to load the plugin. To repair an already-open
SSH editor without restarting it, run:

```vim
:let g:clipboard = 'osc52'
:unlet! g:loaded_clipboard_provider
:runtime autoload/provider/clipboard.vim
```

Run `mise exec -- python3 tests/omarchy-clipboard.py` for selection regressions,
and add `--installed` on Omarchy to exercise both real editor profiles in an
isolated pseudo-terminal. The installed test captures explicit/unnamed OSC 52
yanks and simulates a terminal paste response without changing a real clipboard.

## Deployment

Follow the [shared deployment procedure](omarchy-agents.md#apply): inspect the
actual `~/dev/src/system-config-amfaro` snapshot, compare affected files, transfer
only intended changes, and preserve its separate lockfile and unrelated edits.
A local Mac change or commit does not synchronize that snapshot.

For the initial migration, move the **unmanaged** `~/.config/nvim` directory to
`~/.local/state/nvim-migration/<timestamp>/config` after reviewing its contents.
Preserve the entire directory, including its LazyVim lock and customizations.
Do not force Home Manager links or use blanket automatic backups. Leave existing
`~/.local/share/nvim/lazy` runtime data alone.

Build and activate as `johna` with Bash explicitly over SSH:

```bash
cd ~/dev/src/system-config-amfaro
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
export NIX_CONFIG='extra-experimental-features = nix-command flakes'
nix build --no-write-lock-file \
  'path:.#homeConfigurations."johna@omarchy".activationPackage' \
  --out-link result-nvim
DRY_RUN=1 ./result-nvim/activate
./result-nvim/activate
```

For exact initial plugin revision parity, seed the writable `nvim-pack-lock.json`
inside each new Omarchy config directory from the corresponding Mac profile.
Review/back up any existing lock first; never replace one during routine
activation. Locks are runtime state, not declarative read-only files. Preserve
any existing Omarchy spelling additions rather than replacing them with Mac's.

Start each profile once to install its plugins. Allow Tree-sitter parser installs
to finish before testing. On Omarchy run:

```bash
mise exec -- python3 tests/omarchy-nvim.py --installed
```

The installed test checks both real profiles, theme/keybindings, Pi buffer
recognition, dictionary, dependency resolution, fresh Fish editor selection,
and actual Markdown parsing/formatting/linting/Harper attachment.

Shared editor or lint-config changes also require the Mac's repo-local
`mise update-system --switch-only` and the same installed test there. Do not
restart active editors or agents: reopen an editor to pick up Lua changes, and
start a fresh shell/session for changed editor environment variables.

## Rollback

Record the previous Home Manager generation before activating. Reactivate it to
remove the new configuration links/packages, then restore the preserved native
config directory. Keep the new runtime lock/spelling files safe if they prevent
removing the now-unmanaged config directory. Do not delete user runtime data or
uninstall Home Manager, which also owns Omarchy's other services and agents.
