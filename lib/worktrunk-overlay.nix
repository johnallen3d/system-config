# Keep Mac and Omarchy on the same upstream release while nixpkgs catches up.
# Remove this override once both hosts' locked nixpkgs provide >= 0.80.0.
final: prev: {
  worktrunk = prev.worktrunk.overrideAttrs (finalAttrs: _oldAttrs: {
    version = "0.80.0";
    src = prev.fetchFromGitHub {
      owner = "max-sixty";
      repo = "worktrunk";
      tag = "v${finalAttrs.version}";
      hash = "sha256-wT9V9A6ty4yCp/wJ9F92AC5SrsQzemEb8/d2NSjH/SY=";
    };
    cargoDeps = prev.rustPlatform.fetchCargoVendor {
      inherit (finalAttrs) pname version src;
      hash = "sha256-CVk7tSdt0eh7MtbbMruU1f4664tlnQPjQ2ovXfRcbIA=";
    };
  });
}
