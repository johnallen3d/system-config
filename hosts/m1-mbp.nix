{...}: {
  imports = [
    # can't log with AppleID on virtual machine, therefore can't use mas
    ../modules/darwin/homebrew/mas.nix
  ];
}
