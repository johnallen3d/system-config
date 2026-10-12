{pkgs}:
pkgs.stdenvNoCC.mkDerivation {
  pname = "imdb-enhanced-extension";
  version = "2.22.0";

  src = pkgs.fetchFromGitHub {
    owner = "SysAdminDoc";
    repo = "IMDb_Enhanced";
    rev = "1d6a114b236c511a5a01a407be2cac4244284ceb";
    hash = "sha256-HuHOvqFhT4CiwZsWfBe8n0i1bv2kfbUCz+/p3ya1pmE=";
  };

  nativeBuildInputs = [pkgs.nodejs_24 pkgs.python3];

  # Public identity only, not a signing credential. Keep this unchanged on updates:
  # Chromium otherwise derives the unpacked extension ID from its directory path.
  # This keeps browser-owned settings associated with the same extension even if
  # Arc resolves the Home Manager symlink to a different Nix store generation.
  extensionPublicKey = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsv+/TvrlqRyuAAjxdbajIs74Oo1kDGclE6YG18xhgq3Fc2mf0kDfBcZx2FbbJXHlYkBC+LkAwsL7YgZNyKICKHwUj7k7MFxY85j0w1YmtaWb74Q7VqC8Pe9+VP3uLRs5DgIwKN5EwjlLp66yR52J4UkERwEp3RFdbQuC7tVewXcnAQtFUb87d0eSs/1sDf4h2LugTbxU5OFcmSccPYfPkfPcZJYRc/K8Ereoy05UEiuJ3BAHovAgyd7SK7TXNdLzQyjttRHI6Dxh5a3JWSDh8YEVFftlhVnHznPGx1h7PpQCRVZ77WG1uuXaGkpgPkI7WZk77U5hplyyve8dYoY8PQIDAQAB";

  buildPhase = ''
    runHook preBuild
    # Same build as npm run build:extension; only Node built-ins are used.
    # The shared source is assembled during the build, not installed as a userscript.
    node scripts/build-userscript.js
    node scripts/build-extension.js
    runHook postBuild
  '';

  doCheck = true;
  checkPhase = ''
    runHook preCheck
    node scripts/build-userscript.js --check
    node scripts/build-extension.js --check
    # These extra profiles are test fixtures only; install the Chromium build.
    node scripts/build-extension.js --firefox --store
    node tests/extension.js
    node tests/background.js
    node tests/gm-contract.js
    for script in extension/*.js; do
      node --check "$script"
    done
    runHook postCheck
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/share/imdb-enhanced"
    cp -R extension/. "$out/share/imdb-enhanced/"
    python3 - <<'PY'
    import base64
    import hashlib
    import json
    import os
    from pathlib import Path

    root = Path(os.environ["out"]) / "share/imdb-enhanced"
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["manifest_version"] == 3
    assert manifest["version"] == os.environ["version"]
    manifest["key"] = os.environ["extensionPublicKey"]
    extension_id = "".join(
        chr(ord("a") + int(nibble, 16))
        for nibble in hashlib.sha256(base64.b64decode(manifest["key"])).hexdigest()[:32]
    )
    assert extension_id == "onpcpnooofbhiojkgihepagmggdfikbj"
    resources = [manifest["background"]["service_worker"], manifest["options_ui"]["page"]]
    resources.extend(manifest["icons"].values())
    resources.extend(manifest["action"]["default_icon"].values())
    for script in manifest["content_scripts"]:
        resources.extend(script.get("js", []))
        resources.extend(script.get("css", []))
    resources.append(f'_locales/{manifest["default_locale"]}/messages.json')
    for resource in resources:
        assert (root / resource).is_file(), f"Missing extension resource: {resource}"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Installed Chromium MV3 extension {extension_id}")
    PY
    runHook postInstall
  '';

  meta = {
    description = "IMDb Enhanced standalone Chromium extension (unpacked)";
    homepage = "https://github.com/SysAdminDoc/IMDb_Enhanced";
    license = pkgs.lib.licenses.mit;
    platforms = pkgs.lib.platforms.all;
  };
}
