# Antigravity CLI (agy) for personal work on the Mac and Omarchy only. agy has
# no profiles, so it is never installed on work-only hosts. It runs in
# enterprise-gateway mode against the personal subscription proxy, whose
# Antigravity login lives on Omarchy: no Google credential on any client.
{
  config,
  lib,
  pkgs,
  ...
}: let
  cfg = config.antigravity;
  # Google's release bucket, ahead of nixpkgs-unstable (1.5.13 adds Gemini 4
  # Neon through a gateway). Drop this override once nixpkgs has >= 1.5.13.
  buildId = "5999302598852608";
  sources = {
    aarch64-darwin = {
      platform = "darwin-arm/cli_mac_arm64.tar.gz";
      hash = "sha256-HIPj6Ii1QQxEptilRn9+yg11xNVVHIAHa32o3Hc4vZw=";
    };
    x86_64-linux = {
      platform = "linux-x64/cli_linux_x64.tar.gz";
      hash = "sha256-f6nMbfDQlWJpPWN8QGqGwbD1KrM2RxSx/S15zGBg1LI=";
    };
  };
  source = sources.${pkgs.stdenv.hostPlatform.system};
  unwrapped =
    if lib.versionAtLeast pkgs.antigravity-cli.version "1.5.13"
    then pkgs.antigravity-cli
    else
      pkgs.antigravity-cli.overrideAttrs (finalAttrs: _: {
        version = "1.5.13";
        src = pkgs.fetchurl {
          url = "https://storage.googleapis.com/antigravity-public/antigravity-cli/${finalAttrs.version}-${buildId}/${source.platform}";
          inherit (source) hash;
        };
      });
  # No fallback to a direct Google login: without the proxy key, agy stops.
  agy = pkgs.writeShellApplication {
    name = "agy";
    text = ''
      if ! key="$(${config.home.homeDirectory}/.local/bin/subscription-proxy client-key personal)" || [ -z "$key" ]; then
        echo "agy: personal subscription-proxy client key unavailable; not starting." >&2
        exit 1
      fi
      export AGY_LLM_GATEWAY_URL=${lib.escapeShellArg cfg.gatewayUrl}
      export AGY_LLM_GATEWAY_API_KEY="$key"
      exec ${lib.getExe unwrapped} "$@"
    '';
  };
  mcpServers = {
    switchyard.serverUrl = cfg.switchyardMcpUrl;
  };
in {
  options.antigravity = {
    enable = lib.mkEnableOption "agy routed through the personal subscription proxy";
    gatewayUrl = lib.mkOption {
      type = lib.types.str;
      default = "https://omarchy.taila14c2.ts.net:8443";
      description = "Tailscale Serve HTTPS front of the personal proxy (agy rejects remote plain HTTP).";
    };
    switchyardMcpUrl = lib.mkOption {
      type = lib.types.str;
      default = "http://johns-macbook-pro.taila14c2.ts.net:7391/mcp";
      description = "Switchyard MCP endpoint for spawned agy tasks. No X-Rex-* headers: agy does not expand them.";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = config.subscriptionProxy.enable;
        message = "antigravity needs subscriptionProxy clients for the personal key.";
      }
    ];
    home.packages = [agy];
    # Merge only the switchyard server into agy's MCP config; agy and the user
    # own the rest. settings.json is left writable for Switchyard's
    # trustedWorkspaces.
    home.activation.antigravityMcp = lib.hm.dag.entryAfter ["linkGeneration"] ''
      if [ -z "''${DRY_RUN:-}" ]; then
        ${pkgs.python3}/bin/python3 - "$HOME/.gemini/config/mcp_config.json" ${lib.escapeShellArg (builtins.toJSON mcpServers)} <<'EOF'
      import json, os, sys
      path, servers = sys.argv[1], json.loads(sys.argv[2])
      try:
          with open(path) as f:
              text = f.read()
      except FileNotFoundError:
          text = ""
      data = json.loads(text) if text.strip() else {}
      merged = dict(data, mcpServers={**data.get("mcpServers", {}), **servers})
      if merged != data:
          os.makedirs(os.path.dirname(path), exist_ok=True)
          tmp = path + ".tmp"
          with open(tmp, "w") as f:
              json.dump(merged, f, indent=2)
              f.write("\n")
          os.replace(tmp, path)
      EOF
      fi
    '';
  };
}
