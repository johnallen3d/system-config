# #758 capability tools, private PATH only. No workstation/profile installation.
{ pkgs, runtimePkgs }: let
  py = runtimePkgs.python313Packages;
  taskYaml = py.pyyaml.overridePythonAttrs (_: {
    version = "6.0.2";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/54/ed/79a089b6be93607fa5cdaedf301d7dfb23af5f25c398d5ead2525b063e17/pyyaml-6.0.2.tar.gz";
      sha256 = "d584d9ec91ad65861cc08d42e834324ef890a082e591037abe114850ff7bbc3e";
    };
    doCheck = false;
  });
  taskPython = (runtimePkgs.python313.withPackages (ps: [
    taskYaml ps.pillow ps.pillow-heif ps.reportlab ps.pypdf ps.playwright
  ])).overrideAttrs (_: { version = runtimePkgs.python313.version; });
  notebooklm = py.buildPythonApplication {
    pname = "notebooklm-py";
    version = "0.8.2";
    pyproject = true;
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/89/e0/c605af3764ed9fd9938bf73d771a0b44685ae3edd077aa38351fd5b4d038/notebooklm_py-0.8.2.tar.gz";
      sha256 = "8a427e32b40bc4e96582871f39aaa302de5fd81b9d423c0e109d33190165cd14";
    };
    build-system = [ py.hatchling py.hatch-fancy-pypi-readme ];
    dependencies = [ py.click py.filelock py.httpx py.rich py.playwright ];
    doCheck = false; # Auth/network tests are #760; fixed offline checks test imports/CLI.
    pythonImportsCheck = [ "notebooklm" ];
  };
  # autoPatchelfHook's mutation of this Rust release crashes before --version.
  # Preserve the reviewed bytes and use the pinned native ELF loader explicitly.
  miseRelease = pkgs.fetchurl {
    url = "https://github.com/jdx/mise/releases/download/v2026.9.7/mise-v2026.9.7-linux-x64";
    sha256 = "d479d7c0df37652ddfd6d1887ef92a67a17effc7ec4ac612f46845099f814c6f";
  };
  releaseBinary = { name, version, url, sha256, archive ? false, binary ? name }:
    pkgs.stdenv.mkDerivation {
      pname = "hermes-native-${name}";
      inherit version;
      src = pkgs.fetchurl { inherit url sha256; };
      nativeBuildInputs = [ pkgs.autoPatchelfHook ];
      buildInputs = [ pkgs.stdenv.cc.cc.lib ];
      dontUnpack = !archive;
      unpackPhase = if archive then ''
        mkdir payload
        tar -xzf "$src" -C payload
      '' else null;
      installPhase = if archive then ''
        install -Dm755 payload/${binary} "$out/bin/${name}"
      '' else ''
        install -Dm755 "$src" "$out/bin/${name}"
      '';
    };
in {
  inherit notebooklm;
  # libheif 1.23 renamed the reviewed vault task's converter; preserve its argv.
  heif-convert = (pkgs.writeShellScriptBin "heif-convert" ''
    exec ${pkgs.libheif}/bin/heif-dec "$@"
  '').overrideAttrs (_: { version = pkgs.libheif.version; });
  task-python = taskPython;
  browser-driver = runtimePkgs.playwright-driver;
  pdf = runtimePkgs.poppler-utils;
  # Prebuilt exact PEP723 dependency closure for the two reviewed task scripts.
  # All other uv invocations retain frozen/offline behavior and cannot download.
  uv-task = (pkgs.writeShellScriptBin "uv" ''
    export UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never UV_NO_MANAGED_PYTHON=1
    if [ "$#" -ge 3 ] && [ "$1" = run ] && [ "$2" = --quiet ] && [ "$3" = --script ]; then
      shift 3
    elif [ "$#" -ge 2 ] && [ "$1" = run ] && [ "$2" = --script ]; then
      shift 2
    else
      exec ${runtimePkgs.uv}/bin/uv "$@"
    fi
    [ "$#" -ge 1 ] || exit 64
    script="$1"
    shift
    canonical="$(${runtimePkgs.coreutils}/bin/realpath -e -- "$script")"
    case "$canonical" in
      "''${VAULT_DIR:-/nonexistent}/.mise/tasks/common-foods-browser")
        # This is a writer. Production must use the outer writer adapter; an
        # ordinary read-only plugin invocation must never open this route.
        if [ "''${HERMES_NATIVE_OFFLINE:-}" != 1 ]; then
          [ "''${HERMES_NATIVE_STAGE:-}" = production ] && [ "''${HERMES_PRODUCTION_WRITER_HELD:-}" = 1 ] || exit 64
        fi
        exec ${taskPython}/bin/python3 -I "$canonical" "$@"
        ;;
      "''${VAULT_DIR:-/nonexistent}/scripts/macros-details")
        # Read-only deterministic report; no provider credentials or download.
        if [ "''${HERMES_NATIVE_OFFLINE:-}" != 1 ]; then
          [ "''${HERMES_NATIVE_STAGE:-}" = production ] && [ "''${HERMES_NATIVE_READONLY:-}" = 1 ] || exit 64
        fi
        exec ${taskPython}/bin/python3 -I "$canonical" "$@"
        ;;
      *) exec ${runtimePkgs.uv}/bin/uv run --script "$script" "$@" ;;
    esac
  '').overrideAttrs (_: { version = runtimePkgs.uv.version; });
  uvx-notebooklm = (pkgs.writeShellScriptBin "uvx" ''
    export UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never UV_NO_MANAGED_PYTHON=1
    if [ "$#" -ge 3 ] && [ "$1" = --from ] && [ "$2" = 'notebooklm-py[browser]==0.8.2' ] && [ "$3" = notebooklm ]; then
      shift 3
      exec ${notebooklm}/bin/notebooklm "$@"
    fi
    exec ${runtimePkgs.uv}/bin/uvx "$@"
  '').overrideAttrs (_: { version = runtimePkgs.uv.version; });
  mise = (pkgs.writeShellScriptBin "mise" ''
    exec ${taskPython}/bin/python3 -I ${./task-compat.py} \
      ${pkgs.stdenv.cc.bintools.dynamicLinker} \
      ${pkgs.lib.makeLibraryPath [ pkgs.glibc pkgs.stdenv.cc.cc.lib ]} \
      ${miseRelease} "$@"
  '').overrideAttrs (_: {
    name = "hermes-native-mise-2026.9.7";
    version = "2026.9.7";
  });
  vlt = releaseBinary {
    name = "vlt"; version = "0.11.0"; archive = true;
    url = "https://github.com/paivot-ai/vlt/releases/download/v0.11.0/vlt_0.11.0_linux_amd64.tar.gz";
    sha256 = "c575f7f3c26cd267c4e587b37e7c09a3851e0e9a3e23532c92f78661e696602f";
  };
  gog = releaseBinary {
    name = "gog"; version = "0.40.0"; archive = true;
    url = "https://github.com/openclaw/gogcli/releases/download/v0.40.0/gogcli_0.40.0_linux_amd64.tar.gz";
    sha256 = "5f73815950f30de4165b7b767103ca45c4950e84a1da601eda5294e9ff94f767";
  };
  yq = releaseBinary {
    name = "yq"; version = "4.53.6";
    url = "https://github.com/mikefarah/yq/releases/download/v4.53.6/yq_linux_amd64";
    sha256 = "c5f056448f973ae7d39b5401949648a78f2dc1947d6a8eb65be60d5c504b9385";
  };
  # Lock-resolved native replacements are explicit in runtime.json. Do not pretend
  # Debian build identifiers or a transitive Node closure are byte-identical.
  inherit (pkgs) jq defuddle tesseract libheif util-linux curl cacert sd;
}
