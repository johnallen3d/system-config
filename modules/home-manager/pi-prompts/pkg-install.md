---
description: "Install a package via optimal method. Usage: /pkg-install [nix|pi|brew] <package>"
model: gpt-5.4-mini
skill: pi-nix-integration
subagent: delegate
---

Determine the install method and package name from the arguments:

- If `$1` is one of `nix`, `pi`, or `brew` → method is `$1`, package is `${@:2}`
- Otherwise → method is unknown, package is `$@`, research required

---

<if-model is="anthropic/*,google/*,openai/*">
## Dispatch

**Method**: `$1` | **Args**: `$@`

### Known method (nix | pi | brew)

Skip research. Execute directly.

#### nix

Add `${@:2}` to `modules/home-manager/packages/default.nix` alphabetically in `home.packages`, then:

```bash
mise run nix-rebuild -- --switch-only
which ${@:2} && ${@:2} --version || echo "verify manually"
```

#### pi

Add `"${@:2}"` to `piPackages` list in `modules/home-manager/packages/pi.nix` alphabetically, then:

```bash
mise run nix-rebuild -- --switch-only
pi list | grep "${@:2}"
```

#### brew

Find homebrew config in `modules/darwin/homebrew/`. Add `${@:2}` as `brew` (CLI) or `cask` (app) alphabetically, then:

```bash
mise run nix-rebuild -- --switch-only
brew list | grep "${@:2}"
```

---

### Unknown method — research required

Research `$@` to determine best install method. Priority: **nixpkgs → brew → pi → other**.

1. `nix search nixpkgs $@` — prefer if found and not stale
2. Check if it's a GUI app → brew cask
3. Check if it's a pi extension/skill/theme → pi
4. Fall back to brew formula

Once method determined, follow the appropriate steps above.
</if-model>
