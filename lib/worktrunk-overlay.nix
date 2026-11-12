# Keep Mac and Omarchy on the same upstream release while nixpkgs catches up.
# Remove this override once both hosts' locked nixpkgs provide >= 0.81.0.
final: prev: {
  worktrunk = prev.worktrunk.overrideAttrs (finalAttrs: oldAttrs: {
    version = "0.81.0";
    src = prev.fetchFromGitHub {
      owner = "max-sixty";
      repo = "worktrunk";
      tag = "v${finalAttrs.version}";
      hash = "sha256-Sgim8WgH5nGr1GhSZRtwkRu87b/S2W9gp7eHgtTGBAo=";
    };
    cargoDeps = prev.rustPlatform.fetchCargoVendor {
      inherit (finalAttrs) pname version src;
      hash = "sha256-cJ5rd4+5IIxuUTWWAe5DF2cDU+lyZVMUq+l+I029peU=";
    };
    # Match nixpkgs' 0.81.0 recipe; older recipes (Omarchy's pin) lack these.
    # shell_exec and signal_forwarder tests run python3 as a child process.
    nativeCheckInputs = prev.lib.unique ((oldAttrs.nativeCheckInputs or []) ++ [prev.python3]);
    postPatch = ''
      substituteInPlace src/shell_exec.rs \
        --replace-fail '/usr/bin/python3' 'python3'
    '';
  });
}
