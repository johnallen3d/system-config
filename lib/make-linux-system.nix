{
  home-manager,
  nixpkgs,
  user,
  full_name,
}: {
  host,
  extraModules ? [],
}: let
  system = "aarch64-linux";
  home = "/home/${user}";
in
  nixpkgs.lib.nixosSystem {
    inherit system;
    pkgs = import nixpkgs {
      inherit system;
      config.allowUnfree = true;
    };

    specialArgs = {
      inherit user home full_name;
    };

    modules =
      [
        ../modules/common
        ../modules/linux
        # TODO: check on this?
        ../modules/darwin/environment

        home-manager.nixosModules.home-manager
        {
          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.extraSpecialArgs = {
            inherit user full_name;
          };

          home-manager.users."john.allen".imports = [
            ../modules/home-manager
            ../hosts/${host}.nix
            ../modules/home-manager/packages/linux.nix
          ];
        }
      ]
      ++ extraModules;
  }
