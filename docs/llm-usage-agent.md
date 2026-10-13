# llm-usage background cache for SketchyBar

On macOS, Home Manager runs `org.nix-community.home.llm-usage` as a long-running
launchd user agent. It executes:

```sh
llm-usage json --source cliproxy --interval 60 --output <cache-path>
```

The work proxy URL is derived from `subscriptionProxy.address`, port 8318.
The output path is defined once in `modules/home-manager/default.nix` from
`config.xdg.cacheHome`; SketchyBar receives that same absolute path. launchd
need not inherit `XDG_CACHE_HOME`, Fish, Pi, or Claude profile environment.
SketchyBar only reads JSON: it does not run the CLI, acquire locks, or force a
refresh when clicked. The popup and severity colors are unchanged.

A persistent process preserves proxy discovery state, Claude's five-minute
refresh throttle, Retry-After cooldowns, and stale fallback between polls.
Codex/Go normally refresh every minute; Claude normally refreshes every five
minutes. The package retains the existing durable **local-mode** Claude cache
patch, but explicitly preserves the proxy cache's upstream one-hour expiry:
proxy snapshots now use the same helper, so the local patch otherwise changes
remote behavior and breaks its expiry test.

## One-time Keychain setup (John only)

Use the **work** CLIProxyAPI management key, not its client key or the personal
profile's key. John obtains it privately from the existing subscription-proxy
credentials; agents must not retrieve, print, copy, or handle the key.

Run this yourself in an interactive Mac terminal. Keeping `-w` last prompts for
the password without putting it in shell history or process arguments:

```sh
/usr/bin/security add-generic-password -U \
  -s llm-usage-cliproxy-work -a "$USER" -T /usr/bin/security -w </dev/null
```

Paste the work management key at the hidden prompt. The item is stored in the
default login Keychain; `/usr/bin/security` is explicitly trusted for runtime
reads. Do not use `-A`, supply a literal password argument, or enable shell tracing.

The wrapper reads the item at runtime and exports
`LLM_USAGE_CLIPROXY_MANAGEMENT_KEY` only to the CLI process. The key is never
embedded in the Nix store, launchd plist, arguments, or logs. Like any environment
secret, it is accessible to sufficiently privileged processes; do not dump the
agent environment. If the item is missing or the Keychain is locked, the wrapper
exits and launchd retries with a 60-second throttle. After setup/unlocking:

```sh
launchctl kickstart -k "gui/$(id -u)/org.nix-community.home.llm-usage"
```

## Deploy

The pin is used by the shared desktop Home Manager package list. Omarchy's
standalone `packages/coding-agents.nix` does **not** import that list and does not
currently install `llm-usage`; this change does not silently add it. The service
and SketchyBar wiring are macOS-only. Keep the Omarchy source snapshot coherent
and verify the package can build on Linux without claiming it was installed.
Do not update flake inputs:

### Keep the deployment in the normal rebuild source

The initial migration was deployed and committed on `feature/llm-usage-agent`,
but never integrated into `main`. A later normal rebuild from `main` removed the
service and restored one-shot polling. Installing from a task worktree is only
provisional: obtain John's commit/integration authorization and integrate the
migration into the primary checkout before treating the regression as resolved.
Rebuild from that integrated source and rerun installed verification. Do not
close #748 while integration is pending. Never merge or commit without permission.

### Host application

- Mac: from the checkout/worktree containing the changes, use the repository-local
  `mise update-system --switch-only`, then `sketchybar --reload`. The rebuild task
  resolves its flake root from its own script location, including task worktrees.
- Omarchy: compare the actual task worktree under `~/dev/src/system-config/.worktrees/` before
  transferring intended source changes. Preserve unrelated edits and credentials;
  do not run Mac rebuild tasks there. These edits do not change its active Home
  Manager module/package closure, so no activation is needed. If a later change
  opts its standalone package set into `llm-usage`, follow the build/activation
  workflow in [omarchy-agents.md](omarchy-agents.md#apply).

The launchd job and wrapper use umask 0077, giving new JSON files mode 0600.
Activation creates its cache and state directories with mode 0700, and creates
or restricts the log files to 0600 before launchd opens them. launchd itself
opens logs before applying the job's umask, so the plist setting alone does not
protect newly created logs. JSON replacement is atomic. Old `refresh.lock` and `usage.json.<pid>` files are
no longer used and can be removed manually after switching.

## Verify

```sh
nix flake check
python3 tests/llm-usage-agent.py --evaluate --binary "$(command -v llm-usage)" --installed
launchctl print "gui/$(id -u)/org.nix-community.home.llm-usage" \
  | rg -e 'state =' -e 'last exit'
plutil -p ~/Library/LaunchAgents/org.nix-community.home.llm-usage.plist
bash ~/.config/sketchybar/plugins/llm-usage.sh --test
```

The plist must contain only `LLM_USAGE_CLIPROXY_URL` in its environment, not a
management key or Pi/Claude profile variables. The isolated binary test supplies
no key and uses a temporary home: it verifies repeated private JSON output and
explicit proxy-source errors without touching real credentials or providers.

For the default cache location:

```sh
jq -c '.providers[] | {provider, status, source, error}' ~/.cache/llm-usage/usage.json
/usr/bin/stat -f '%Sp %Sm' ~/.cache/llm-usage/usage.json
```

Expect `source: "cliproxy"`, successful or stale provider usage, mode
`-rw-------`, and an mtime advancing about every minute. If `xdg.cacheHome` is
customized, use the substituted `cache=` path in the installed plugin instead.
Confirm the bar label and the Codex, OpenCode Go, and Claude Code popup rows.
On Omarchy, verify the built binary's `json --help` support for `--interval` and
`--output`, and run the isolated `--binary` test. Check installed packages
independently: absence of `llm-usage` in the current standalone configuration is
expected, not proof that its package pin was deployed to a runtime.

Do not close the card while required deployment or snapshot synchronization is
pending, or while Keychain setup and authenticated runtime verification remain
incomplete.
