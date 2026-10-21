{
  description = "nix-darwin and home-manager configuration";

  inputs = {
    # Deliberately not following nixpkgs: the derivation must match what CI pushed to Cachix.
    credits.url = "github:johnallen3d/credits/main";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # #781: retain Omarchy's deployed inputs without downgrading other hosts.
    # Updating these pins is a separate, reviewed deployment/identity change.
    omarchyNixpkgs.url = "github:NixOS/nixpkgs/151fa4e8ddfdd8dd25d945ad94ed54a13de9f6e4";
    omarchyHomeManager = {
      url = "github:nix-community/home-manager/fae6e9e42c3b762ab47635cddcfaf6f52374a61b";
      inputs.nixpkgs.follows = "omarchyNixpkgs";
    };
    omarchyHerdrProjectPicker = {
      url = "github:johnallen3d/herdr-project-picker/70219b8e1157f85dab8a8b9cf3b67907e6ca969d";
      flake = false;
    };
    hermes = {
      # Native staging foundation (#755); upstream owns its sealed Python/npm locks.
      url = "github:NousResearch/hermes-agent/a19160bbf02dc37c57ff47cf0eaa4a3ab8ee43dc";
      # Deliberately retain upstream's locked package inputs, independent of host locks.
    };
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
    herdrProjectPicker = {
      url = "github:johnallen3d/herdr-project-picker";
      flake = false;
    };
  };

  outputs = {
    credits,
    home-manager,
    herdrProjectPicker,
    hermes,
    lop,
    nix-darwin,
    nixpkgs,
    yem,
    omarchyNixpkgs,
    omarchyHomeManager,
    omarchyHerdrProjectPicker,
    ...
  }: let
    user = "john.allen";
    full_name = "John Allen";

    makeDarwinSystem = import ./lib/make-darwin-system.nix {
      inherit credits home-manager herdrProjectPicker lop nix-darwin nixpkgs yem user full_name;
    };
    makeNixosSystem = import ./lib/make-nixos-system.nix {
      inherit home-manager herdrProjectPicker lop nixpkgs yem user full_name;
    };
    makeHomeManagerSystem = import ./lib/make-home-manager-system.nix {
      inherit home-manager herdrProjectPicker lop nixpkgs yem user full_name;
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
      # Keep Omarchy isolated from the shared dotfiles and desktop setup.
      "johna@omarchy" = omarchyHomeManager.lib.homeManagerConfiguration {
        pkgs = import omarchyNixpkgs {
          system = "x86_64-linux";
          overlays = [(import ./lib/worktrunk-overlay.nix)];
        };
        extraSpecialArgs = {
          inherit credits hermes lop;
          herdrProjectPicker = omarchyHerdrProjectPicker;
        };
        modules = [./hosts/omarchy.nix];
      };
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
