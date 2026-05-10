---
description: "Install a package via optimal method. Usage: /pkg-install [nix|pi|brew] <package>"
argument-hint: "[nix|pi|brew] <package>"
model: haiku
---

Determine the install method and package name from `$ARGUMENTS`:

- If the first whitespace-separated token is one of `nix`, `pi`, or `brew` → method is that token, package is the rest of `$ARGUMENTS`.
- Otherwise → method is unknown, package is the full `$ARGUMENTS`, research required.

---

## Dispatch

### Known method (nix | pi | brew)

Skip research. Execute directly.

#### nix

Add the package to `modules/home-manager/packages/default.nix` alphabetically in `home.packages`, then:

```bash
mise run nix-rebuild -- --switch-only
which <pkg> && <pkg> --version || echo "verify manually"
```

#### pi

Add `"<pkg>"` to the `piPackages` list in `modules/home-manager/packages/pi.nix` alphabetically, then:

```bash
mise run nix-rebuild -- --switch-only
pi list | grep "<pkg>"
```

#### brew

Find homebrew config in `modules/darwin/homebrew/`. Add the package as `brew` (CLI) or `cask` (app) alphabetically, then:

```bash
mise run nix-rebuild -- --switch-only
brew list | grep "<pkg>"
```

---

### Unknown method — research required

Research the package to determine best install method. Priority: **nixpkgs → brew → pi → other**.

1. `nix search nixpkgs <pkg>` — prefer if found and not stale.
2. Check if it's a GUI app → brew cask.
3. Check if it's a pi extension/skill/theme → pi.
4. Fall back to brew formula.

Once method is determined, follow the appropriate steps above.
