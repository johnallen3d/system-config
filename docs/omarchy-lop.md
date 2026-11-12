# Lop on Omarchy

Tracked in Fizzy [#721](https://app.fizzy.do/6284043/cards/721) (installation)
and [#723](https://app.fizzy.do/6284043/cards/723) (Mac configuration parity).

`hosts/omarchy.nix` opts into Lop without changing Omarchy's native desktop.
Its `~/.config/lop/config.toml` uses the same Nix-owned source as the Mac:
`~/dev/src`, scan depth 3, fetch timeout 60 seconds, and `check_processes = false`.
The Lop input is pinned to the revision used by the Mac's installed package,
including sibling `exclusions.toml` support.

Scheduled pruning is disabled on every host ([#1100](https://app.fizzy.do/6284043/cards/1100)):
the Mac's `lop schedule` agent is uninstalled and Linux hosts no longer declare
`lop.service`/`lop.timer`. Run `lop scan` or `lop prune` manually when needed.

`~/.config/lop/exclusions.toml` stays writable and host-local, matching the Mac's
ownership. Review it when repositories move or new host-specific exclusions are
needed.

Linux package overrides keep the full test suite enabled while replacing the
fixture's `/bin/cat` with Nix coreutils and serializing flaky executable-fixture
tests. Upstream cleanup is tracked in [#722](https://app.fizzy.do/6284043/cards/722).
