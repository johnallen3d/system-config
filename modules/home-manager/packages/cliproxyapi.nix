# Pin the central proxy independently of either host's nixpkgs lock.
{pkgs}:
pkgs.cliproxyapi.overrideAttrs (finalAttrs: _oldAttrs: {
  version = "8.0.23";
  src = pkgs.fetchFromGitHub {
    owner = "router-for-me";
    repo = "CLIProxyAPI";
    tag = "v${finalAttrs.version}";
    hash = "sha256-7SDLiut4/+7uZr1Usaq887r7TZNPdJA6rwmrdzgxTXQ=";
  };
  vendorHash = "sha256-r3yWkdMcM40G9jV7MxW/qNv3E9WrHavFilW24quEf+8=";
})
