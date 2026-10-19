# A bounded browser-client trial; keep upstream's complete compatible Pi stack.
{pkgs}: let
  source = pkgs.fetchFromGitHub {
    owner = "TannerMidd";
    repo = "pi-pocket";
    rev = "26542deded0123d6b217828ed2f71f566d9a7a19";
    hash = "sha256-bdys/0mSXTzelK3URo2DHmfaUIKdHSCRdWvqeJEZAY0=";
  };
  upstream = pkgs.callPackage "${source}/nix/package.nix" {
    # Neither a public tunnel nor an agent-controlled browser belongs in this spike.
    cloudflared = pkgs.emptyDirectory;
    chromium = pkgs.emptyDirectory;
  };
in
  upstream.overrideAttrs (old: {
    # Preserve John's /search and /food UX, without relaxing other command names.
    postPatch = (old.postPatch or "") + ''
      substituteInPlace src/server/extension-web.ts --replace-fail \
        'typeof name !== "string" || !COMMAND_NAME.test(name)' \
        'typeof name !== "string" || (!COMMAND_NAME.test(name) && !((name === "search" && part.file === "notes-search.ts") || (name === "food" && part.file === "notes-food.ts")))'
      # The notes CLI already has a /food prompt template. Only while our exact
      # command is enabled, omit that name from Pocket's template catalog so the
      # browser routes it to the helper command. The CLI template is untouched,
      # other templates retain precedence, and disabling the module restores it.
      substituteInPlace src/server/app.ts --replace-fail \
        $'return loadPromptTemplates(cwd, getAgentDir(), paths, {\n            project: !projectDistrusted(cwd, this.#skillSources()),\n        });' \
        $'const templates = loadPromptTemplates(cwd, getAgentDir(), paths, {\n            project: !projectDistrusted(cwd, this.#skillSources()),\n        });\n        const foodCommand = this.webs.commands().some(command => command.name === "food" && this.webs.command(command.id)?.file === "notes-food.ts");\n        return foodCommand ? templates.filter(template => template.name !== "food") : templates;'
      # Command cards have no browser-renderer hook upstream. Limit this UI
      # adapter to complete /search food tables; all other cards stay untouched.
      cp ${./pi-pocket-search.js} web/notes-search.js
      substituteInPlace web/transcript.js --replace-fail \
        'import { Component } from "preact";' \
        'import { Component } from "preact"; import { foodSearchRows, FoodSearchCard } from "./notes-search.js";'
      substituteInPlace web/transcript.js --replace-fail \
        'function CommandEntry({ entry }) {' \
        'function CommandEntry({ entry }) {
          const results = entry.command === "search" && !entry.clipped && !entry.truncated ? foodSearchRows(entry.output) : null;
          if (results) return html`<''${FoodSearchCard} entry=''${entry} results=''${results} />`;'
      cat >> web/style.css <<'CSS'
      .notes-food-search { overflow-x: auto; }
      .notes-food-search table { border-collapse: collapse; font: 12px/1.7 var(--mono); }
      .notes-food-search th, .notes-food-search td { text-align: left; padding: 2px 12px 2px 0; }
      .notes-food-search pre { margin: 0; font: inherit; white-space: pre; }
      .notes-food-key { display: flex; align-items: center; gap: 6px; }
      .notes-food-key code { white-space: nowrap; }
      .notes-food-key button { min-width: 36px; min-height: 36px; flex-shrink: 0; }
      CSS
    '';
    # Only the spike's queue/stop/reconnect/persistence cases, using a faux model.
    # The full upstream suite needs Chromium and unrelated optional integrations.
    checkPhase = ''
      runHook preCheck
      node --test --test-name-pattern='a tab gets the queue|sessions and artifacts survive|each conversation sends its own provider session id' test/app.test.ts
      runHook postCheck
    '';
    # Upstream's extension-reload test has stale exact response-shape assertions.
    # Test our actual installed HTTP/auth/SQLite boundary without that feature.
    installCheckPhase = ''
      runHook preInstallCheck
      "$out/bin/pi-pocket" --help
      PI_POCKET_TEST_PACKAGE="$out" node --test ${../../../tests/pi-pocket-package.mjs}
      runHook postInstallCheck
    '';
    passthru = {
      revision = "26542deded0123d6b217828ed2f71f566d9a7a19";
      piVersion = "1.1.0";
    };
  })
