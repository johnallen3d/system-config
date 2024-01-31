{
  home-manager,
  nix-darwin,
  nixpkgs,
}: {
  system,
  user,
  home,
  brew_bin,
  full_name,
}: {
  host,
  extraModules ? [],
}:
nix-darwin.lib.darwinSystem {
  inherit system;
  pkgs = import nixpkgs {inherit system;};
  specialArgs = {
    inherit brew_bin;
    inherit home;
    inherit user;
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
            inherit brew_bin;
            inherit full_name;
            inherit home;
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
