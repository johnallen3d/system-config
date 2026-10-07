# Omarchy: standalone Home Manager proof of concept

Tracked in [Fizzy #688](https://app.fizzy.do/6284043/cards/688).

The results below describe the original isolated POC. The current host profile
also manages an opt-in [VNC user service](omarchy-vnc.md). Uninstalling the
whole Home Manager profile would remove that service too; do not repeat the
POC teardown on a host with additional managed resources unintentionally.

Host: Omarchy 4.0.4 (Arch-based), `x86_64-linux`; SSH: `johna@omarchy`;
home: `/home/johna`. This is not a NixOS conversion.

The `johna@omarchy` flake output imports only `hosts/omarchy.nix`, not the
shared package/dotfile suite. It installs Nix-managed `jq` and the Home Manager
CLI, and links `~/.config/nix-home-manager-poc/status.json`. Home Manager also
creates its profile/session-variable support and XDG `.keep` placeholders.
Shell configuration, Hyprland, Omarchy themes, GPU integration, MIME databases,
and user systemd management are deliberately excluded. Arch's `/usr/bin/jq`
remains installed; use the explicit Nix profile path below to prove ownership.

## Verified outcome

Live testing on Omarchy succeeded with Nix 2.35.2:

- Native build, activation dry-run, activation, and repeat activation passed.
- Profile `jq` resolves into `/nix/store`; Arch's `/usr/bin/jq` still works.
- A second generation changed the test marker; reactivating the first restored it.
- Home Manager uninstall removed the marker, POC executables, and XDG placeholder
  links; reactivation successfully restored the original POC.
- All 25 recorded shell/desktop file fingerprints remained unchanged, including
  after the Nix bootstrap. The flake lock and host module were also unchanged.

The original POC was restored after testing. This proves standalone user-level
package/dotfile management on Omarchy, not GUI/GPU or full-system management.
Application configuration and package compatibility outside this scope still
need their own testing.

## One-time Nix bootstrap (interactive sudo required)

Run on Omarchy, as `johna`, not root:

```bash
ssh -t johna@omarchy
sh <(curl -fsSL https://nixos.org/nix/install) --daemon --no-channel-add --no-modify-profile
```

The official multi-user installer adds `/nix`, build users, the Nix daemon,
`/etc/nix/nix.conf`, and global shell integration. `--no-modify-profile` is not
a guarantee against global `/etc` changes; the Home Manager POC itself does
not manage shell startup files. Review the installer's plan before confirming.
Do not grant passwordless sudo just for this POC.

For the current experiment, an uncommitted working-tree snapshot is staged at
`~/dev/src/system-config-poc`, and a pre-install shell/desktop fingerprint is
stored at `~/.cache/nix-home-manager-poc/baseline.sha256`. The snapshot has now
been built and activated. Test logs are also in that cache directory.

## Build and apply on Omarchy (no sudo)

```bash
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
export NIX_CONFIG='extra-experimental-features = nix-command flakes'
cd ~/dev/src/system-config-poc

# path: includes the staged working tree without needing a git commit.
nix build --no-write-lock-file \
  'path:.#homeConfigurations."johna@omarchy".activationPackage' \
  --out-link result
./result/activate
```

A fresh clone can use the same commands from its own checkout after these
changes are committed. No lock update or separate Home Manager channel is
needed. Do not use `-b backup` or force file replacement: unexpected collisions
should stop activation instead of overwriting Omarchy configuration.

## Verify and repeat

```bash
jq_bin=$(readlink -f "$HOME/.nix-profile/bin/jq")
case "$jq_bin" in /nix/store/*/bin/jq) ;; *) exit 1 ;; esac
"$HOME/.nix-profile/bin/jq" --version

test -L "$HOME/.config/nix-home-manager-poc/status.json"
"$HOME/.nix-profile/bin/jq" -e \
  '.host == "omarchy" and .managedBy == "home-manager" and .scope == "isolated-cli-poc"' \
  "$HOME/.config/nix-home-manager-poc/status.json"

# Reapplying the same generation must succeed without creating conflicts.
./result/activate

# Compare the original shell and desktop file list and contents.
{
  sha256sum "$HOME/.bashrc" "$HOME/.bash_profile"
  find "$HOME/.config/hypr" "$HOME/.config/omarchy" -type f -exec sha256sum {} +
} | sort > /tmp/omarchy-poc-after.sha256
cmp "$HOME/.cache/nix-home-manager-poc/baseline.sha256" /tmp/omarchy-poc-after.sha256
```

The shell features flag above affects only this session. Home Manager does not
source its generated session variables because it does not own Bash here.

## Prove rollback

On the disposable snapshot only:

```bash
initial_generation=$(readlink -f result)
cp hosts/omarchy.nix /tmp/omarchy-poc-host-original.nix
sed -i 's/isolated-cli-poc/isolated-cli-poc-v2/' hosts/omarchy.nix
nix build --no-write-lock-file \
  'path:.#homeConfigurations."johna@omarchy".activationPackage' \
  --out-link result-v2
./result-v2/activate
"$HOME/.nix-profile/bin/jq" -e '.scope == "isolated-cli-poc-v2"' \
  "$HOME/.config/nix-home-manager-poc/status.json"

"$initial_generation/activate"
"$HOME/.nix-profile/bin/jq" -e '.scope == "isolated-cli-poc"' \
  "$HOME/.config/nix-home-manager-poc/status.json"
cp /tmp/omarchy-poc-host-original.nix hosts/omarchy.nix
```

## Remove Home Manager's POC resources

This host had no previous Home Manager profile. If that changes, do not
uninstall another configuration. Resolve the locked sources explicitly so
uninstall does not require channels:

```bash
nixpkgs_path=$(nix eval --impure --raw --expr \
  "(builtins.getFlake \"path:$PWD\").inputs.nixpkgs.outPath")
hm_path=$(nix eval --impure --raw --expr \
  "(builtins.getFlake \"path:$PWD\").inputs.home-manager.outPath")
"$HOME/.nix-profile/bin/home-manager" \
  -I "nixpkgs=$nixpkgs_path" -I "home-manager=$hm_path" uninstall

test ! -e "$HOME/.config/nix-home-manager-poc/status.json"
test ! -L "$HOME/.config/nix-home-manager-poc/status.json"
```

Confirm the uninstall prompt. Nix itself, cached store paths, generation
history, and this source snapshot remain; this is not a Nix uninstaller.
