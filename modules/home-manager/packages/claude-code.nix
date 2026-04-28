{
  lib,
  stdenv,
  buildNpmPackage,
  fetchzip,
  versionCheckHook,
  writableTmpDirAsHomeHook,
  bubblewrap,
  procps,
  socat,
}:
buildNpmPackage (finalAttrs: {
  pname = "claude-code";
  version = "2.1.119";

  src = fetchzip {
    url = "https://registry.npmjs.org/@anthropic-ai/claude-code/-/claude-code-${finalAttrs.version}.tgz";
    hash = "sha256-niZddQ0t40dzR0nXlj5Onkxy0apq5wvvPvhjQvr96cw=";
  };

  npmDepsHash = "sha256-rKp3mMCc4xyYMdQBgFr8FPpjrOcMgkP6Ied5ijfdN58=";

  strictDeps = true;

  postPatch = ''
    cp ${./claude-code-package-lock.json} package-lock.json
  '';

  dontNpmBuild = true;

  env.AUTHORIZED = "1";

  # Replace the stub with the native binary, then disable self-updates;
  # Nix owns the installed version.
  postInstall = ''
    pushd $out/lib/node_modules/@anthropic-ai/claude-code
    node install.cjs
    popd
    rm -f $out/bin/claude
    ln -s $out/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe $out/bin/claude

    wrapProgram $out/bin/claude \
      --set DISABLE_AUTOUPDATER 1 \
      --set-default FORCE_AUTOUPDATE_PLUGINS 1 \
      --set DISABLE_INSTALLATION_CHECKS 1 \
      --unset DEV \
      --prefix PATH : ${
      lib.makeBinPath (
        [
          # claude-code uses node-tree-kill, which needs pgrep(darwin) or ps(linux).
          procps
        ]
        ++ lib.optionals stdenv.hostPlatform.isLinux [
          bubblewrap
          socat
        ]
      )
    }
  '';

  doInstallCheck = true;
  nativeInstallCheckInputs = [
    writableTmpDirAsHomeHook
    versionCheckHook
  ];
  versionCheckKeepEnvironment = ["HOME"];

  meta = {
    description = "Agentic coding tool that lives in your terminal, understands your codebase, and helps you code faster";
    homepage = "https://github.com/anthropics/claude-code";
    downloadPage = "https://www.npmjs.com/package/@anthropic-ai/claude-code";
    license = lib.licenses.unfree;
    mainProgram = "claude";
    sourceProvenance = with lib.sourceTypes; [binaryBytecode];
  };
})
