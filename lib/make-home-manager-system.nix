{
  home-manager,
  nixpkgs,
  user,
  full_name,
}: {
  host,
  system,
  extraModules ? [],
}: let
  home = "/home/${user}";
  pkgs = import nixpkgs {
    inherit system;
    config.allowUnfree = true;
  };
in
  home-manager.lib.homeManagerConfiguration {
    inherit pkgs;

    extraSpecialArgs = {
      inherit home user full_name;
      op_path = "${pkgs._1password-cli}/bin/op";
      op_ssh_sign_path = "${pkgs._1password-gui}/bin/op-ssh-sign";
    };

    modules =
      [
        ../modules/common/home-manager.nix
        ../modules/home-manager
        ../hosts/${host}.nix
        ../modules/home-manager/packages/linux.nix
        {
          home = {
            username = user;
            homeDirectory = "/home/${user}";
          };
        }
      ]
      ++ extraModules;
  }
