{
  description = "nix-darwin and home-manager configuration";

  inputs = {
    # nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
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
    makeNixosSystem = import ./lib/make-nixos-system.nix {
      inherit home-manager nixpkgs user full_name;
    };
    makeHomeManagerSystem = import ./lib/make-home-manager-system.nix {
      inherit home-manager nixpkgs user full_name;
    };
  in {
    darwinConfigurations = {
      m4-mbp = makeDarwinSystem {
        host = "m4-mbp";
        extraModules = [
          ./modules/darwin/homebrew/mas.nix
        ];
      };

      macos-virtual = makeDarwinSystem {
        host = "macos-virtual";
      };
    };

    nixosConfigurations = {
      drummer = makeNixosSystem {
        host = "drummer";
      };
    };

    homeConfigurations = {
      "john.allen@xcel" = makeHomeManagerSystem {
        system = "aarch64-linux";
        host = "xcel";
      };
      "john.allen@pi-01" = makeHomeManagerSystem {
        system = "aarch64-linux";
        host = "pi-01";
      };
    };
  };
}
