---
description: Install a package via optimal method. Usage: /pkg-install [nix|pi|brew] <package>
model: claude-haiku-4-5
skill: pi-nix-integration
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
sudo darwin-rebuild switch --flake ".#m4-mbp" --impure
which ${@:2} && ${@:2} --version || echo "verify manually"
```

#### pi
Add `"${@:2}"` to `piPackages` list in `modules/home-manager/packages/pi.nix` alphabetically, then:
```bash
sudo darwin-rebuild switch --flake ".#m4-mbp" --impure
rm -f ~/.pi/packages-installed
pi list | grep "${@:2}"
```

#### brew
Find homebrew config in `modules/darwin/homebrew/`. Add `${@:2}` as `brew` (CLI) or `cask` (app) alphabetically, then:
```bash
sudo darwin-rebuild switch --flake ".#m4-mbp" --impure
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
