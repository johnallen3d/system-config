{
  home-manager,
  nix-darwin,
  nixpkgs,
}: {
  host,
  extraModules ? [],
}: let
  system = "aarch64-darwin";
  user = "john.allen";
  home = "/Users/${user}";
  brew_bin = "/opt/homebrew/bin";
  full_name = "John Allen";
in
  nix-darwin.lib.darwinSystem {
    inherit system;
    pkgs = import nixpkgs {inherit system;};
    specialArgs = {
      inherit brew_bin home user;
    };
    modules =
      [
        ../modules/darwin
        home-manager.darwinModules.home-manager
        {
          home-manager = {
            useGlobalPkgs = true;
            useUserPackages = true;
            extraSpecialArgs = {
              inherit brew_bin full_name home;
            };
            users.${user}.imports = [
              ../modules/home-manager
              ../hosts/${host}.nix
            ];
          };
        }
      ]
      ++ extraModules;
  }
