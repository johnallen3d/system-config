# Arc extensions managed by Home Manager

## IMDb Enhanced

The `m4-mbp` Home Manager configuration imports `arc-extensions.nix`. Arc itself
is already installed through the Darwin Homebrew module. This extension is
macOS-only configuration: Omarchy and the other hosts do not import it.

Home Manager installs the **standalone Chromium Manifest V3 extension**, not a
userscript or userscript manager, at:

```text
~/.local/share/browser-extensions/imdb-enhanced
```

The source is pinned by commit and hash in
`modules/home-manager/packages/imdb-enhanced-extension.nix`. Its build uses
Node built-ins directly, without npm installation or network access during the
build. Upstream assembles shared source internally before generating the native
extension; no `.user.js` file is installed for the browser to load.

The package runs upstream extension, background-worker, and storage-bridge tests,
checks JavaScript syntax, and verifies the installed manifest resources. This is
not a full security audit or a live Arc compatibility test.

### First install in Arc

1. Apply from the checkout containing the changes, without updating inputs:
   `mise exec -- mise run update-system --switch-only`.
2. Open `arc://extensions` (use `chrome://extensions` if Arc does not recognize
   the alias).
3. Enable **Developer mode** and click **Load unpacked**.
4. In the folder picker, press **Cmd+Shift+G** and enter the stable path above
   (or `/Users/john.allen/.local/share/browser-extensions/imdb-enhanced`).
   Select that folder, not its resolved `/nix/store` target.
5. Confirm **IMDb Enhanced** appears, is enabled, and has no extension errors.
6. Reload an IMDb title page. Use its gear icon to configure the extension;
   the extension toolbar action also opens its settings/recovery page.

Home Manager manages the files, **not browser installation consent**. There is
no Arc extension-installation module in this setup. We do not overwrite Arc's
Preferences, Secure Preferences, extension databases, or browser-owned data to
simulate installation, and do not assume Arc supports Chrome enterprise policies.
The first load and any required browser permission prompts are manual steps.

Initially the extension requests IMDb access. Its manifest also declares local
storage, unlimited storage, clipboard writes, alarms, and request-blocking
permissions. Additional sites and notifications are optional and requested by
features that need them. Review those prompts; keep integration credentials in
the extension's UI, never Nix or repository files. Browser-local preferences,
private marks, caches, and credentials are not managed by Home Manager.

### Updates and rollbacks

1. Change the source commit/hash and package version together in
   `imdb-enhanced-extension.nix`, after reviewing upstream changes. Keep the
   public manifest identity key unchanged.
2. Build/test and apply using the repository's macOS apply task with
   `--switch-only`. There is no automatic extension source update or browser reload.
3. Click **Reload** on IMDb Enhanced in `arc://extensions`, then refresh IMDb.
4. Confirm the extension version matches the installed manifest and no errors
   appear. If Arc retained a resolved old `/nix/store` path, use **Load unpacked**
   again with the stable Home Manager path and verify the version again.
   Do not remove the extension as an update mechanism: removal can erase its data.

The fixed public manifest key gives this managed build the extension ID
`onpcpnooofbhiojkgihepagmggdfikbj`, independent of Nix store generations. It is a
public identity, not a signing credential; no private key is kept. The stable ID
helps preserve browser-owned settings across reloads, but is not a substitute for
backups. Use the extension's Data/settings recovery page to export important
marks before upgrades. An installed-file rollback likewise needs a browser reload;
rolling back files does not roll back browser-local data migrations.

If another IMDb Enhanced installation is present, back it up before switching.
Enable only one copy to avoid duplicate page modifications.
