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
  op_path = "${brew_bin}/op";
  op_ssh_sign_path = "/Applications/1Password.app/Contents/MacOS/op-ssh-sign";
in
  nix-darwin.lib.darwinSystem {
    inherit system;
    pkgs = import nixpkgs {
      inherit system;
      config.allowUnfree = true;
      overlays = [ (final: prev: {
        actionlint = let version = "1.7.7"; in prev.stdenv.mkDerivation {
          pname = "actionlint";
          inherit version;
          src = prev.fetchurl {
            url = "https://github.com/rhysd/actionlint/releases/download/v${version}/actionlint_${version}_darwin_arm64.tar.gz";
            # NOTE: fill in real hash after first failed build
            hash = "sha256-JpMxW5CTrqy069kamT/qVPwhUFe/DaJlkFa0vAM4c9s=";
          };
          sourceRoot = ".";
          nativeBuildInputs = [];
          buildInputs = [];
          dontBuild = true;
          installPhase = ''
            runHook preInstall
            mkdir -p $out/bin
            install -m755 actionlint $out/bin/
            runHook postInstall
          '';
          meta = prev.actionlint.meta // {
            description = "actionlint prebuilt binary (temp nokogiri workaround)";
            broken = false;
          };
        };
        # Temporary workaround for fish pexpect test failures on darwin
        # See: https://github.com/NixOS/nixpkgs/issues/461406
        fish = prev.fish.overrideAttrs (old: {
          doCheck = false;
        });
      }) ];
    };
    specialArgs = {
      inherit brew_bin home user;
    };
    modules =
      [
        ../modules/common/nix-darwin.nix
        ../modules/darwin
        home-manager.darwinModules.home-manager
        {
          home-manager = {
            useGlobalPkgs = true;
            useUserPackages = true;
            extraSpecialArgs = {
              inherit brew_bin full_name home op_path op_ssh_sign_path;
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
