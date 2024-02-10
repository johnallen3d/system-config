{
  home-manager,
  nix-darwin,
  nixpkgs,
  user,
  full_name,
}: {
  host,
  extraModules ? [],
}: let
  system = "aarch64-darwin";
  home = "/Users/${user}";
  brew_bin = "/opt/homebrew/bin";
  op_ssh_sign_path = "/Applications/1Password.app/Contents/MacOS/op-ssh-sign";
in
  nix-darwin.lib.darwinSystem {
    inherit system;
    pkgs = import nixpkgs {inherit system;};
    specialArgs = {
      inherit brew_bin home user;
    };
    modules =
      [
        ../modules/common
        ../modules/darwin
        home-manager.darwinModules.home-manager
        {
          home-manager = {
            useGlobalPkgs = true;
            useUserPackages = true;
            extraSpecialArgs = {
              inherit brew_bin full_name home op_ssh_sign_path;
            };
            users.${user}.imports = [
              ../modules/home-manager
              ../modules/home-manager/fish/path_fix.nix
              ../hosts/${host}.nix
            ];
          };
        }
      ]
      ++ extraModules;
  }
