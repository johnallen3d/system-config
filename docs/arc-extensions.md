# Arc extension removal

## IMDb Enhanced

IMDb Enhanced is no longer managed by this repository. It was removed because
it did not work reliably in Arc. Its Home Manager module and pinned extension
package have been removed; Arc itself remains installed.

This extension was macOS-only: Omarchy and other hosts never imported it and
need no activation for this removal.

Apply the removal from the checkout containing these changes, without updating
flake inputs:

```sh
mise exec -- mise run update-system --switch-only
```

Home Manager removes the managed unpacked-extension path:

```text
~/.local/share/browser-extensions/imdb-enhanced
```

Home Manager does **not** uninstall extensions from Arc. Arc may have retained a
resolved `/nix/store` path, and a running extension can remain active after the
managed symlink is removed. Complete the browser removal in every Arc profile
where it was loaded:

1. If needed, export important marks or settings from the extension before
   removing it; removal can erase its browser-local data.
2. Open `arc://extensions` (or `chrome://extensions`).
3. Find **IMDb Enhanced**, click **Remove**, and confirm removal.
4. Reload open IMDb tabs so previously injected page changes are discarded.
5. Confirm IMDb Enhanced is no longer listed and the managed path above is gone.

Do not edit Arc's Preferences, Secure Preferences, extension databases, or other
browser-owned data to simulate uninstallation. No browser profile or credentials
are managed by this repository.
