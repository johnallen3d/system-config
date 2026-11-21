{
  description = "nix-darwin and home-manager configuration";

  inputs = {
    # Deliberately not following nixpkgs: the derivation must match what CI pushed to Cachix.
    credits.url = "github:johnallen3d/credits/main";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager = {
      # Stay on Home Manager master while nixpkgs tracks nixos-unstable.
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nix-darwin = {
      url = "github:LnL7/nix-darwin";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    lop = {
      url = "github:johnallen3d/lop";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    yem = {
      # Upstream is private and still named cue; use Git's configured credentials.
      url = "git+https://github.com/johnallen3d/cue.git?ref=main";
      flake = false;
    };
    rex = {
      # Pre-release; fetching needs the netrc from modules/home-manager/nix-netrc.nix.
      url = "https://pkgs.superlogical.com/rex/nix/snapshot.tar.gz";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # Subscription proxy data, locked like any input and bumped by update-system.
    cliproxyModels = {
      url = "github:router-for-me/models";
      flake = false;
    };
    cliproxyPanel = {
      url = "file+https://github.com/router-for-me/Cli-Proxy-API-Management-Center/releases/latest/download/management.html";
      flake = false;
    };
    switchyard = {
      # The Rex float tools (~/dev/src/playground/switchyard). Develop against
      # the checkout with --override-input switchyard path:<checkout>.
      # Keep its own nixpkgs so the package matches what CI pushed to Cachix.
      url = "github:johnallen3d/switchyard";
    };
  };

  outputs = {
    credits,
    home-manager,
    lop,
    nix-darwin,
    nixpkgs,
    yem,
    cliproxyModels,
    cliproxyPanel,
    rex,
    switchyard,
    ...
  }: let
    user = "john.allen";
    full_name = "John Allen";

    makeDarwinSystem = import ./lib/make-darwin-system.nix {
      inherit cliproxyModels cliproxyPanel credits home-manager lop nix-darwin nixpkgs switchyard yem user full_name;
    };
    makeHomeManagerSystem = import ./lib/make-home-manager-system.nix {
      inherit cliproxyModels cliproxyPanel home-manager lop nixpkgs switchyard yem user full_name;
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

    homeConfigurations = let
      # Keep Omarchy (Arch) hosts isolated from the shared dotfiles and desktop setup.
      makeOmarchyHome = host:
        home-manager.lib.homeManagerConfiguration {
          pkgs = import nixpkgs {
            system = "x86_64-linux";
            overlays = [(import ./lib/worktrunk-overlay.nix)];
          };
          extraSpecialArgs = {
            inherit cliproxyModels cliproxyPanel credits full_name host lop rex switchyard;
          };
          modules = [./hosts/${host}.nix];
        };
      # pi-cielo homelab hosts (Debian): Rex server only, deployed separately.
      makeHomelabHome = {
        host,
        user,
        system,
      }:
        home-manager.lib.homeManagerConfiguration {
          pkgs = import nixpkgs {inherit system;};
          extraSpecialArgs = {inherit host rex user;};
          modules = [./hosts/homelab-common.nix];
        };
    in {
      "beelink@nas" = makeHomelabHome {
        host = "nas";
        user = "beelink";
        system = "x86_64-linux";
      };
      "pi@pi-01" = makeHomelabHome {
        host = "pi-01";
        user = "pi";
        system = "aarch64-linux";
      };
      "pi@pi-02" = makeHomelabHome {
        host = "pi-02";
        user = "pi";
        system = "aarch64-linux";
      };
      "pi@pi-03" = makeHomelabHome {
        host = "pi-03";
        user = "pi";
        system = "aarch64-linux";
      };
      "johna@drummer" = makeOmarchyHome "drummer";
      "johna@miller" = makeOmarchyHome "miller";
      "johna@omarchy" = makeOmarchyHome "omarchy";
      "john.allen@xcel" = makeHomeManagerSystem {
        system = "aarch64-linux";
        host = "xcel";
      };
    };
  };
}
