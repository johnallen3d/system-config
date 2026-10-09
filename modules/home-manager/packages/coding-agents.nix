# Small opt-in package set for standalone Linux agent hosts, not the desktop suite.
{pkgs, ...}: let
  pi = import ./pi.nix {inherit pkgs;};
  runtimePath = pkgs.lib.makeBinPath [pkgs.nodejs_24 pkgs.git pkgs.python3 pkgs.ripgrep pkgs.uv];
  claude = pkgs.writeShellScriptBin "claude" ''
    export PATH="${runtimePath}:$PATH"
    export CLAUDE_CONFIG_DIR="''${CLAUDE_CONFIG_DIR:-$HOME/.config/claude-personal}"
    export CLAUDE_CODE_DISABLE_1M_CONTEXT=0
    export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1
    exec ${pkgs.claude-code}/bin/claude "$@"
  '';
  managedPi = pkgs.writeShellScriptBin "pi" ''
    export PATH="${runtimePath}:$PATH"
    # Omarchy provides a global libvips. Sharp otherwise switches from its
    # bundled binaries to a source build requiring undeclared build tooling.
    export SHARP_IGNORE_GLOBAL_LIBVIPS=1
    # Headroom's pip-installed native wheels need the C++/zlib runtimes that
    # Nix Python does not find in Arch's /usr/lib. Scope this to Pi and its
    # children (including the extension-managed proxy), not the login shell
    # or Claude. Keep the extension's venv installation/lifecycle unchanged.
    export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath [pkgs.stdenv.cc.cc.lib pkgs.zlib]}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export PI_CODING_AGENT_DIR="''${PI_CODING_AGENT_DIR:-$HOME/.config/pi}"
    if [ -z "''${CLAUDE_CONFIG_DIR:-}" ]; then
      if [ "$PI_CODING_AGENT_DIR" = "$HOME/.config/pi-work" ]; then
        export CLAUDE_CONFIG_DIR="$HOME/.config/claude-gmatter"
      else
        export CLAUDE_CONFIG_DIR="$HOME/.config/claude-personal"
      fi
    fi
    exec ${pi}/bin/pi "$@"
  '';
  workSetup = pkgs.writeShellScriptBin "agent-work-setup" ''
    set -euo pipefail
    export PATH="${runtimePath}:$PATH"
    export PI_CODING_AGENT_DIR="$HOME/.config/pi-work"
    export CLAUDE_CONFIG_DIR="$HOME/.config/claude-gmatter"
    # Fail early with Git's auth instructions, before partially installing.
    git ls-remote https://github.com/amfaro/agent-kit HEAD >/dev/null
    ${managedPi}/bin/pi install git:github.com/amfaro/agent-kit
    if ${claude}/bin/claude plugin marketplace list --json | ${pkgs.jq}/bin/jq -e 'any(.[]; .name == "amfaro")' >/dev/null; then
      ${claude}/bin/claude plugin marketplace update amfaro
    else
      ${claude}/bin/claude plugin marketplace add amfaro/agent-kit
    fi
    if ${claude}/bin/claude plugin list --json | ${pkgs.jq}/bin/jq -e 'any(.[]; .id == "agent-kit@amfaro")' >/dev/null; then
      ${claude}/bin/claude plugin update agent-kit@amfaro
    else
      ${claude}/bin/claude plugin install agent-kit@amfaro --scope user
    fi
    echo "Work agent-kit installed. Restart Claude Code."
  '';
  commands = {
    inherit claude;
    pi = managedPi;
    agent-work-setup = workSetup;
  };
in {
  nixpkgs.config.allowUnfreePredicate = pkg: pkgs.lib.getName pkg == "claude-code";

  home.packages =
    pkgs.lib.attrValues commands
    ++ (with pkgs; [
      git
      nodejs_24
      python3
      ripgrep
      uv
    ]);

  # Omarchy already puts ~/.local/bin in PATH; do not rewrite its shell startup.
  # Existing unmanaged launchers must be reviewed/backed up before activation.
  home.file = pkgs.lib.mapAttrs' (name: package:
    pkgs.lib.nameValuePair ".local/bin/${name}" {
      source = "${package}/bin/${name}";
    })
  commands;
}
