# Herdr favorite projects

Tracked in [Fizzy #702](https://app.fizzy.do/6284043/cards/702).

The shared catalog is
`modules/home-manager/dotfiles/config/herdr/plugins/config/herdr.project-picker/projects.toml`.
Both Mac and Omarchy install the same generated picker configuration. Personal
and work sessions retain their scoped favorites; the `default` session (used by
Omarchy's persistent server) gets the combined list. Each source entry has:

- `path`: the same home-relative location on both hosts (`~/dev/src/...`).
- `clone_url`: the Git source used only when that location is missing.

`herdr-projects.nix`, imported by the shared Herdr module, clones missing favorites
at Home Manager activation. GitHub sources use HTTPS and the machine's existing
Git credentials. Nothing is fetched during the Nix build. Existing repository
roots and worktrees are left untouched: no fetch, pull, checkout, remote changes,
or deletion. Non-repository collisions fail rather than overwrite user data.
Failed clones are cleaned up and can be retried by reapplying Home Manager.

Edit the catalog in this repository and apply each host. The picker's
`add-current` action can replace its managed symlink; persistent additions need
both `path` and `clone_url` in the repository catalog.

## Local-only pi-cielo seed

`pi-cielo` has no Git remote. Its source is a machine-local Git bundle at
`~/.local/share/herdr/project-seeds/pi-cielo.bundle`. The initial Omarchy setup
copies a bundle of committed refs/history from the Mac, not working files,
credentials, or worktrees. The bundle is not tracked here or put in the Nix store.
A bundle-seeded checkout has no `origin` remote, matching the Mac repository.

On another fresh host, supply that bundle before activation (or replace its
`clone_url` with a real remote after one is explicitly configured). An existing
checkout needs no bundle, and the bundle is never used to synchronize updates.

## Apply and validate

Mac: `mise update-system --switch-only`.
Omarchy: use the standalone Home Manager activation in
[the Herdr guide](omarchy-herdr.md#apply-and-operate), then reload Herdr config.
Do not stop active Herdr servers.

`python3 tests/herdr-favorite-projects.py` tests provisioning in disposable homes.
After applying, check that every catalog path resolves to its own repository root
and that both hosts have the same managed picker catalog. Commits and branches
may differ: this ensures availability, not synchronization.
