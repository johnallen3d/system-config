---
description: "Install a package via optimal method. Usage: /pkg-install [nix|pi|brew] <package>"
argument-hint: "[nix|pi|brew] <package>"
model: haiku
---

Interpret `$ARGUMENTS` before acting:

- Split arguments on whitespace.
- If the first token is exactly `nix`, `pi`, or `brew`, that token is the install method and the remaining text is the package query.
- Otherwise, method is unknown and the full `$ARGUMENTS` string is the package query.
- If the package query is empty, ask the user what package to install.
- If the package query is a URL, extract the likely package/app name from the URL path or install page, but keep the URL as evidence during research.

Goal: install declaratively in this nix-managed repo. When method is unknown, prefer **nixpkgs → brew → pi → other**.

---

## Dispatch

### Known method (nix | pi | brew)

Skip research only after normalizing the package query.

#### nix

Add the package to `modules/home-manager/packages/default.nix` alphabetically in `home.packages`, then:

```bash
mise run nix-rebuild -- --switch-only
which <pkg> && <pkg> --version || echo "verify manually"
```

#### pi

Add the package spec to `personalPackageSpecs` in `modules/home-manager/pi/packages.nix` alphabetically.
Use `npm:<pkg>` for npm packages unless the source clearly requires another spec such as `git:...`, then:

```bash
mise run nix-rebuild -- --switch-only
pi list | grep "<pkg>"
```

#### brew

Update `modules/darwin/homebrew/default.nix`.
Add any required tap plus the brew formula or cask alphabetically, then:

```bash
mise run nix-rebuild -- --switch-only
brew list | grep "<pkg>"
```

---

### Unknown method — research required

1. Normalize the package query first. Example: `https://github.com/getagentseal/codeburn#install` → package `codeburn`.
2. Search nixpkgs for the normalized name first.
3. If not in nixpkgs, decide whether it is a Homebrew formula/cask, a Pi extension/skill/theme, or another install type.
4. Use upstream install docs to confirm the canonical package name, required taps, or required package spec.
5. Once method is determined, follow the matching flow above.

Do not stop at the raw URL. Extract the installable package/app name and use the URL only to verify install instructions.
