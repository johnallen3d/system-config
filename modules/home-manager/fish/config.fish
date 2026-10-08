# no need for a greeting
set fish_greeting

# Strip transient npx shims so managed wrappers win consistently.
set clean_path
for path_entry in $PATH
    if not string match -qr -- '/\.npm/_npx/[^/]+/node_modules/\.bin$' "$path_entry"
        set clean_path $clean_path $path_entry
    end
end
set -gx PATH $clean_path

# Global (not universal) user paths stay ahead when mise updates PATH.
fish_add_path --global --move --prepend $HOME/.nix-profile/bin
fish_add_path --global --move --prepend /nix/var/nix/profiles/default/bin
fish_add_path --global --move --prepend $HOME/.local/bin
fish_add_path --move --path $HOME/.cargo/bin
fish_add_path --prepend $HOME/.npm-global/bin

if test (uname) = Darwin
    fish_add_path --append /Applications/Obsidian.app/Contents/MacOS
end

# use 1Password to authenticate `gh`
if test -e ~/.config/op/plugins.sh
    source ~/.config/op/plugins.sh
end

if command -q nix-your-shell
    nix-your-shell fish | source
end

if command -q leadr
    leadr --fish | source
end
if command -q mise
    mise activate fish | source
end

# Mise's first environment hook may restore Omarchy's system-first PATH.
# Keep managed wrappers and tools ahead of Arch/Homebrew executables.
fish_add_path --global --move --prepend /nix/var/nix/profiles/default/bin
fish_add_path --global --move --prepend $HOME/.nix-profile/bin
fish_add_path --global --move --prepend $HOME/.local/bin

if command -q tv
    tv init fish | source
end

# Mise refreshes PATH on directory changes; restore managed tools last.
function __fish_prefer_managed_paths --on-variable PWD
    fish_add_path --global --move --prepend /nix/var/nix/profiles/default/bin
    fish_add_path --global --move --prepend $HOME/.nix-profile/bin
    fish_add_path --global --move --prepend $HOME/.local/bin
end
__fish_prefer_managed_paths

fish_config theme choose tokyo-night-moon
