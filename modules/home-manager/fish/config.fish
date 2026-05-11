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

fish_add_path --move --prepend --path $HOME/.nix-profile/bin
fish_add_path --move --prepend --path /nix/var/nix/profiles/default/bin
fish_add_path --move --path $HOME/.cargo/bin

# TODO: can we find a better/more nix way?
fish_add_path --prepend $HOME/.npm-global/bin
fish_add_path --append /Applications/Obsidian.app/Contents/MacOS

# use 1Password to authenticate `gh`
if test -e ~/.config/op/plugins.sh
    source ~/.config/op/plugins.sh
end

if command -q nix-your-shell
    nix-your-shell fish | source
end

leadr --fish | source
mise activate fish | source
tv init fish | source

fish_config theme choose tokyo-night-moon
