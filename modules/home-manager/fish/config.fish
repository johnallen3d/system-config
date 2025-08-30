# no need for a greeting
set fish_greeting

fish_add_path --move --prepend --path $HOME/.nix-profile/bin
fish_add_path --move --prepend --path /nix/var/nix/profiles/default/bin
fish_add_path --move --path $HOME/.cargo/bin

# TODO: can we find a better/more nix way?
fish_add_path --prepend $HOME/.npm-global/bin

# use 1Password to authenticate `gh`
if test -e ~/.config/op/plugins.sh
    source ~/.config/op/plugins.sh
end

if command -q nix-your-shell
    nix-your-shell fish | source
end

sk --shell fish | source
fish_config theme choose tokyo-night-moon
