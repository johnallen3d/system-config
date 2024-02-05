{...}: {
  imports = [
    # kitty not loading in virtual machine 😢
    ../modules/home-manager/kitty
    # TODO: this leaves sketchybar out of macos-virtual
    ../modules/home-manager/packages/darwin.nix
  ];
}
