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
    user = "john.allen";
    full_name = "John Allen";

    makeDarwinSystem = import ./lib/make-darwin-system.nix {
      inherit home-manager nix-darwin nixpkgs user full_name;
    };
    makeLinuxSystem = import ./lib/make-linux-system.nix {
      inherit home-manager nixpkgs user full_name;
    };
  in {
    darwinConfigurations = {
      m1-mbp = makeDarwinSystem {
        host = "m1-mbp";
        extraModules = [
          ./modules/darwin/homebrew/mas.nix
          # TODO: this leaves sketchybar out of macos-virtual
          ./modules/home-manager/packages/darwin.nix
        ];
      };

      macos-virtual = makeDarwinSystem {
        host = "macos-virtual";
      };
    };

    nixosConfigurations = {
      drummer = makeLinuxSystem {
        host = "drummer";
      };
    };
  };
}
