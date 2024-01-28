{
  description = "nix-darwin and home-manager configuration";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nix-darwin = {
      url = "github:LnL7/nix-darwin";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    home-manager,
    nix-darwin,
    nixpkgs,
    ...
  }: let
    arch = "aarch64-darwin";
    full_name = "John Allen";
    user = "john.allen";
    home = "/Users/${user}";
    brew_bin = "/opt/homebrew/bin";
  in {
    darwinConfigurations = {
      m1-mbp = nix-darwin.lib.darwinSystem {
        system = arch;
        pkgs = import nixpkgs {system = arch;};
        specialArgs = {
          inherit brew_bin;
          inherit home;
          inherit user;
        };
        modules = [
          ./modules/darwin
          # can't log with AppleID on virtual machine
          # therefore can only use mas here
          ./modules/darwin/homebrew/mas.nix
          home-manager.darwinModules.home-manager
          {
            home-manager = {
              useGlobalPkgs = true;
              useUserPackages = true;
              extraSpecialArgs = {
                inherit brew_bin;
                inherit full_name;
                inherit home;
              };
              users.${user}.imports = [
                ./modules/home-manager
                ./hosts/m1-mbp.nix
              ];
            };
          }
        ];
      };

      "macos-virtual" = nix-darwin.lib.darwinSystem {
        system = arch;
        pkgs = import nixpkgs {system = arch;};
        specialArgs = {
          inherit brew_bin;
          inherit home;
          inherit user;
        };
        modules = [
          ./modules/darwin
          home-manager.darwinModules.home-manager
          {
            home-manager = {
              useGlobalPkgs = true;
              useUserPackages = true;
              extraSpecialArgs = {
                inherit brew_bin;
                inherit full_name;
                inherit home;
              };
              users.${user}.imports = [
                ./modules/home-manager
                ./hosts/macos-virtual.nix
              ];
            };
          }
        ];
      };
    };
  };
}
