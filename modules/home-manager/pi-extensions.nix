# Consolidated pi agent extensions.
#
# To add a new extension:
#   1. Add an entry to `extensions` below
#   2. Drop its package-lock.json into packages/<name>-package-lock.json
#   3. Use a dummy npmDepsHash, run `nix-rebuild --switch-only`, grab the real hash from the error
#
{pkgs, ...}: let
  mkPiExtension = {
    pname,
    version,
    url ? "https://registry.npmjs.org/${pname}/-/${pkgs.lib.lists.last (pkgs.lib.splitString "/" pname)}-${version}.tgz",
    hash,
    npmDepsHash,
    lockfile,
    description ? "",
    homepage ? "",
    forceEmptyCache ? false,
  }:
    pkgs.buildNpmPackage {
      inherit pname version npmDepsHash forceEmptyCache;

      src = pkgs.fetchurl {inherit url hash;};

      sourceRoot = "package";
      dontNpmBuild = true;

      postPatch = ''
        cp ${lockfile} package-lock.json
      '';

      installPhase = ''
        runHook preInstall
        mkdir -p $out
        cp -r ./* $out/
        runHook postInstall
      '';

      meta = with pkgs.lib; {
        inherit description homepage;
        license = licenses.mit;
      };
    };

  extensions = {
    pi-mcp-adapter = mkPiExtension {
      pname = "pi-mcp-adapter";
      version = "2.2.2";
      hash = "sha512-aT7eKpjYP558ZiYrlmCABNTuzUiw8eRY10rpgrygsZWfdfo5eC51Jc+NuB0V+lZ+5uGHwPJcZLPadmeO1zXQSA==";
      npmDepsHash = "sha256-qMI9QnIYXvq8JMVrR8zcGNhO2caSSvo1Pq71PR9IjGM=";
      lockfile = ./packages/pi-mcp-adapter-package-lock.json;
      description = "MCP adapter extension for pi coding agent";
      homepage = "https://github.com/nicobailon/pi-mcp-adapter";
    };

    pi-tasks = mkPiExtension {
      pname = "@tintinweb/pi-tasks";
      version = "0.4.2";
      hash = "sha256-XXZCs/7yJfSz0aY5DeW87n8beJwg9tEmm+cJa0y4YVQ=";
      npmDepsHash = "sha256-1tmviUr/xYFebp5kV+59HiGlZIdfLqpkqqHSYUiZq8A=";
      lockfile = ./packages/pi-tasks-package-lock.json;
      description = "Task tracking and coordination for pi coding agent";
      homepage = "https://github.com/tintinweb/pi-tasks";
    };

    pi-markdown-preview = mkPiExtension {
      pname = "pi-markdown-preview";
      version = "0.9.6";
      hash = "sha256-5C/EjaIzZMIpx5u1x1NO/Z4gZqmsda/TGNpnnHe5mP4=";
      npmDepsHash = "sha256-/hHvhFRkhfW8FqTGVbD+u9s2G+E/ZHo93Bd1m5XrCJw=";
      lockfile = ./packages/pi-markdown-preview-package-lock.json;
      description = "Markdown preview renderer for pi coding agent";
      homepage = "https://github.com/thesved/pi-markdown-preview";
    };

    pi-tokyo-night-storm = mkPiExtension {
      pname = "pi-tokyo-night-storm";
      version = "1.0.0";
      hash = "sha256-CwRmlhMlIeEJN8D0tQ+S6TGVbPBBJEWZs5jUxfE6QPY=";
      npmDepsHash = "sha256-Aeyt2zVmx1UpOVZ8T8dRWRPf9uu+Pau8fKkAxWf6tDQ=";
      lockfile = ./packages/pi-tokyo-night-storm-package-lock.json;
      description = "Tokyo Night Storm theme for pi coding agent";
      homepage = "https://github.com/mariozechner/pi-tokyo-night-storm";
      forceEmptyCache = true;
    };

    pi-web-access = mkPiExtension {
      pname = "pi-web-access";
      version = "0.10.6";
      hash = "sha256-93u8a41wgsyK1v2XUuxkycwjbFiP4ToOjBUqPmO4wtk=";
      npmDepsHash = "sha256-zwH9ba5M6wRtyTdpi/7To/ZzkQfNvgO8CxdpGCeB8Vo=";
      lockfile = ./packages/pi-web-access-package-lock.json;
      description = "Web access extension for pi coding agent";
      homepage = "https://github.com/mariozechner/pi-web-access";
    };
  };
in {
  home.file =
    pkgs.lib.mapAttrs'
    (name: pkg:
      pkgs.lib.nameValuePair ".pi/agent/extensions/${name}" {source = pkg;})
    extensions;
}
