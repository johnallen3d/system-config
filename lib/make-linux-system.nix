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
  pkgs = import nixpkgs {
    inherit system;
    config.allowUnfree = true;
  };
in
  nixpkgs.lib.nixosSystem {
    inherit system;

    specialArgs = {
      inherit user home full_name;
    };

    modules =
      [
        ../modules/common
        ../modules/linux

        home-manager.nixosModules.home-manager
        {
          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.extraSpecialArgs = {
            inherit user full_name;
            op_ssh_sign_path = "${pkgs._1password-gui}/bin/op-ssh-sign";
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
