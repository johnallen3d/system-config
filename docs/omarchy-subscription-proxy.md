# Central subscription logins on Omarchy

Tracked in [Fizzy #720](https://app.fizzy.do/6284043/cards/720). The services and
**official Management Center** live on Omarchy. A thin panel launcher and
profile-specific client plumbing are Home Manager-owned on Mac and Omarchy.
There is no custom OAuth/login/key editor: use the upstream panel.

## Accounts and separation

- Personal service: personal Codex OAuth, port 8317.
- Work service: work Codex OAuth, work Claude OAuth, work OpenCode Go key, port 8318.
- Personal Pi: personal Codex only.
- Work Pi: work Codex and curated non-Claude Go models.
- Work Claude Code: the work proxy's Anthropic endpoint. Claude is not used in Pi.

CLIProxyAPI is pinned to source **8.0.23** and official Management Center to
**1.26.0**, independently of either host's nixpkgs lock. The official HTML asset
is hash-pinned in Nix, served from an immutable store path, and not auto-updated.

Both services bind only to Omarchy's Tailscale IPv4 address `100.97.112.40`.
Mac and Omarchy use the same endpoints; no SSH tunnels, public/LAN listeners,
or Funnel. If the machine is removed/re-enrolled in the tailnet, update
`subscriptionProxy.address`, reapply both hosts, and verify it. Tailscale must
be online; systemd retries a failed bind on startup.

Instances have disjoint client/management keys, configs, auth/state paths, and
no cross-account fallback. This prevents accidental account/billing mixing;
it is not a security boundary against processes running as John. Work client
keys are not per-provider ACLs. Pi has explicit non-Claude model entries rather
than blindly importing the work gateway's mixed-provider catalog.

## Log into the OFFICIAL UI

On the Mac (or an Omarchy desktop terminal):

```bash
subscription-proxy ui work
subscription-proxy ui personal
```

Bare `subscription-proxy` opens the work panel. These commands only select the
endpoint, copy its management key to the local clipboard, and open the official
panel. They do not implement provider login, callback handling, status screens,
or key editing. No secret is put in the URL, command arguments, or terminal
output. Paste the copied key into **Management Key** and log in; clear the
clipboard afterward. The management key is not a provider API key.

Direct URLs, when the management key is already saved in that browser:

- Work: `http://100.97.112.40:8318/management.html`
- Personal: `http://100.97.112.40:8317/management.html`

The panel manages one isolated instance at a time. Each port is a separate
browser origin, preserving separate connection/key contexts. Use separate
browser account profiles for work/personal OAuth approvals. There is no native
named-profile collection in the pinned TUI; a small endpoint launcher is enough.

### Work panel

1. Use the **OAuth** section to authenticate the work **Codex** account.
2. Authenticate the work **Claude** account in that same section.
3. In the provider configuration, edit the seeded OpenAI-compatible provider
   **`opencode-go`** and add the work Go API key. Its endpoint, `go` prefix,
   curated model mappings, and session/user-agent forwarding are already seeded.
4. Verify the displayed account/workspace identities before using the routes.

#### Add OpenCode Go after OAuth

1. [Sign into the OpenCode console](https://opencode.ai/auth) and obtain an API
   key for the **work Go subscription**. Leave optional **Use balance** off to
   avoid paid-credit fallback.
2. Run `subscription-proxy ui work`. Open **AI Providers**, find the existing
   **OpenAI Compatible** provider **`opencode-go`**, and choose **Edit**.
3. Under **API key entries**, choose **Add key entry**, paste the Go key into
   **API key**, and **Save**. Keep the preseeded endpoint
   `https://opencode.ai/zen/go/v1`, prefix `go`, models, and headers unchanged.
   Do not add a second primary provider or use the pay-as-you-go Zen endpoint.
4. Ask the operator to reconcile central routing and verify live Go calls from
   both hosts before using the subagents. Pi uses `subscription-go/go/<model>`;
   no upstream key belongs in Pi. Daily jobs keep model choices synchronized.

### Personal panel

Authenticate only **personal Codex**. Do not add work Claude, work Go, or any
work account to this instance.

If a browser on the Mac redirects to localhost and cannot connect, copy the
complete final callback URL into the official panel's callback field. The panel
submits it to Omarchy over Tailscale; no forwarding tunnel is needed. OAuth
sessions are short-lived; retry an expired flow from the panel. Do not paste
callbacks, provider keys, or management keys into agent chat/cards.

ALL upstream credentials, including Claude, are stored only on Omarchy. Native
Claude Code on either host uses the work proxy's client key for its selected
route, not independently managed upstream Claude OAuth credentials.

Go is API-key authentication, not OAuth. The endpoint is
`https://opencode.ai/zen/go/v1`, not pay-as-you-go Zen. Leave OpenCode Console's
optional **Use balance** setting off unless paid-credit fallback is wanted.
The initial bootstrap has `glm-5.2`, `kimi-k2.6`, and `deepseek-v4-flash`.
The catalog reconciler expands this from Go-specific upstream metadata. Pi uses
Chat Completions to the gateway; the gateway selects Chat Completions, Responses,
or Messages **upstream per model**, including non-Claude Messages models.
It forwards Pi's `session_id` to `x-opencode-session` and preserves its user agent
on all three paths. Do not remove those headers when editing the primary key.

Provider/employer policies still apply. Technical proxy OAuth support is not a
provider endorsement of subscription credential intermediation.

## Repeatable Go catalog refresh

Tracked in [Fizzy #725](https://app.fizzy.do/6284043/cards/725), related to #720.
This automation is Home Manager-owned, not an ad-hoc mise task or another login UI.

Sources are the public Go availability endpoint (`/zen/go/v1/models`) and the
**`opencode-go`** record from `https://models.dev/api.json`. The latter supplies
per-model SDK/protocol, context/output limits, reasoning, tools, modalities,
and nominal cost metadata. Never substitute Zen metadata for a missing Go entry.
Only available text/tool-capable models with known protocols are published;
Claude IDs/names/families and unknown metadata are excluded. An advertised ID
without trustworthy Go metadata is quarantined, not guessed. The initial
verified expanded snapshot contains 34 models across all three protocols;
10 legacy/undocumented IDs are pending metadata in
[Fizzy #730](https://app.fizzy.do/6284043/cards/730), and Claude is excluded.

**Daily scheduling on both hosts:**

- Omarchy: `subscription-proxy-catalog.timer`, daily at 03:15 local time plus up
  to ten minutes jitter, five-minute boot catch-up, and persistent missed-run
  catch-up. Its oneshot service reconciles central routing and local work Pi.
- Mac: `org.nix-community.home.subscription-proxy-catalog`, at login/load and
  every 86,400 seconds while loaded. It updates only local work Pi from validated
  public metadata intersected with the running gateway's `go/` model aliases.
  It does not download the upstream Go key or edit central routing.
- Jobs explicitly set paired `PI_CODING_AGENT_DIR`/`CLAUDE_CONFIG_DIR` work
  variables. They never run inference, restart agents, update flake inputs,
  change selected models/defaults/subagent roles, or refresh Pi packages.

Manual refresh (operator; no need to run on both hosts when the daily jobs suffice):

```bash
# Omarchy only: routing plus local Pi
subscription-proxy refresh-go --server
# Mac: local Pi, after the central routes are published
subscription-proxy refresh-go
# Replay the exact last successful public-source inputs without downloading them
subscription-proxy refresh-go --server --cached  # Omarchy
subscription-proxy refresh-go --cached           # Mac
```

`~/.config/subscription-proxy/go-catalog.json` is the private, replayable last-good
public-source snapshot and normalized model/exclusion list. Future Home Manager
activations use it, rather than resetting Pi to the three bootstrap models.
Output caps are conservatively limited to 32,768; context, reasoning, supported
Pi text/image inputs, and nominal cost data come from the metadata. Costs shown
in Pi are estimates, **not a promise of Go overage billing**; leave Use balance off.

The central primary **`opencode-go`** remains the official-UI key editor. Its
Chat Completions model list and required session/User-Agent headers are managed.
The reconciler maintains two derived groups using that same Go key **only on
Omarchy**: **`opencode-go-responses`** in the native xAI/Responses section and
**`opencode-go-messages`** in the native Claude/Messages section. These API
protocol labels do not mean GPT routes use Codex OAuth or Qwen/MiniMax routes
use Claude subscription credentials. Their prefixes/models are disjoint and
all endpoints remain under `/zen/go`. Do not edit derived keys/model lists;
rotate the original key, then run central refresh (or wait for its next run).
The Messages group uses a **per-key `x-api-key` header**, because Go requires it
and CLIProxyAPI otherwise uses only Bearer auth on non-Anthropic hosts. Each
pooled/rotated key has its own correct header; these values stay in Omarchy's
private configuration and never enter the public-source/Pi snapshots.
Removing/disabling the primary clears derived keys on successful refresh.
Use `--cached` to propagate key changes even when public metadata is unavailable.

Fetch/schema/empty-catalog failures and suspicious reductions larger than half
retain last-good Pi choices. Review large legitimate retirements before using
`--allow-shrink`. Local flock prevents overlapping refresh/activation jobs. Activation waits for
an already-running bounded refresh, since a persistent timer can start during
the Home Manager switch; duplicate refreshes fail safely and can be retried.
Central changes use the protected management API and preserve unrelated provider
entries, keys, OAuth configuration, and settings. A second read detects operator
edits before patching, but v8 has **no conditional-write/CAS API**: do not save
provider edits in the panel simultaneously with a refresh. A failed gateway
publication rolls back only if those lists still match the reconciler's write;
it never rolls back over a detected subsequent operator edit. A private central
`go-routing-rollback.json` holds the prior affected lists (including keys), never
in Git, Nix, or the Mac. Tailnet outages leave Mac's last-good choices in place.

Inspect job status without dumping secret configuration:

```bash
# Omarchy
systemctl --user status subscription-proxy-catalog.timer subscription-proxy-catalog.service
journalctl --user -u subscription-proxy-catalog.service -n 10 --no-pager
# Mac
launchctl print gui/$(id -u)/org.nix-community.home.subscription-proxy-catalog
```

Job logs contain counts/redacted errors, not keys or request bodies. New Pi
sessions load refreshed models; use Pi's `/reload` or restart an existing agent
at your discretion. Existing sessions retain their selected model. Neither
model-router virtual-model legacy routing nor Claude Code selection is changed
by this automation.

## Select clients after provisioning and verification

Initial activation installs optional providers but does not switch running
agents/native defaults. Once account identities and minimal live provider calls
have been verified, the operator selects routes on BOTH client hosts:

```bash
subscription-proxy activate personal
subscription-proxy activate work
subscription-proxy activate work --claude
```

Selection is host-local and guarded by the selected client's central OAuth
readiness. Work Pi's Codex route can be selected before adding the Go key.
Its Go subagents are also mapped to the proxy immediately, but will fail until
that key is configured; they never retain a silent native/direct Go fallback.
Presence/readiness alone does not prove inference works. Restart agents in the
intended directory when convenient, never automatically merely to refresh env.

Pi adds `subscription-codex` and work-only `subscription-go`, preserving unrelated
user providers. Client keys are resolved by a command at request time, not
embedded in Nix. Selected work subagents use `subscription-go/go/<model>`.
`PI_CODING_AGENT_DIR` and `CLAUDE_CONFIG_DIR` still come from the shared Amfaro
mise context. Use explicit `mise exec` for noninteractive work commands.

Claude selection changes only its work profile's relevant environment settings:
`ANTHROPIC_BASE_URL` is the work server root, `ANTHROPIC_AUTH_TOKEN` is a proxy
client key, and `ANTHROPIC_API_KEY` is cleared. Permissions/hooks/sessions and
other settings are preserved. No upstream example's permission-bypass settings
are copied. Existing native auth files remain untouched, not copied or deleted.

Private `selected.json` records host-local selections for future Home Manager
activation. Configuration/credential runtime data never belongs in Git.

## Runtime ownership and operations

`~/.config/subscription-proxy/credentials.json` (0600) contains proxy client and
management keys. Mac receives only those keys, never upstream subscription
OAuth tokens. Keep them out of screenshots/logs/source control.

Omarchy's private configs are `server-personal.yaml` and `server-work.yaml` in
that directory; upstream credential files are under
`~/.local/share/subscription-proxy/{personal,work}/auth` (0700). Panel edits to
provider keys persist. Nonsecret listener/security policy is reapplied; auth/state
is never declaratively replaced. The seeded Go entry is created only if absent.

```bash
systemctl --user status subscription-proxy-personal subscription-proxy-work
systemctl --user restart subscription-proxy-personal subscription-proxy-work
```

Do not stream service logs: OAuth handlers may log sensitive material. Inspect
only targeted lifecycle errors when needed. Request logging, discovery, plugins,
and profiling remain disabled; the panel is enabled with auto-updates disabled.
Do not download upstream credential files for client provisioning.

Apply using [Omarchy's standalone procedure](omarchy-agents.md) and Mac's
repo-local `mise update-system --switch-only`. Inspect actual remote source and
installed state before synchronization; preserve unrelated edits and Omarchy's
lockfile. A Mac rebuild is not an Omarchy deployment.

## Rollback and validation

```bash
subscription-proxy deactivate personal
subscription-proxy deactivate work
subscription-proxy deactivate work --claude
```

This restores only owned client settings from a private host-local rollback
record, preserving unrelated changes. Restart affected agents when convenient.
Central logins are not revoked. Revoke upstream tokens separately when
removing/decommissioning the gateway.

Tests:

- `subscription-proxy.py`: temporary-home private state/client/UI-launch tests,
  using Python with PyYAML (the manager's Nix-provided interpreter).
- `subscription-proxy-installed.py`: installed Tailscale/auth/state checks and
  exact official-panel content hash; use `--server` on Omarchy.
- `subscription-proxy-protocol.py`: isolated real proxy against a loopback mock,
  testing the panel's v8 configuration/OAuth API and Go routing/session headers.
- `subscription-proxy-pi.mjs`: each host's actual Pi runtime model loader/key
  resolution, mock tool streaming, and conversation header emission.

Live Codex/Claude/Go calls and effective client/no-fallback checks on BOTH hosts
are still required after approvals. Any pending login, host deployment, or
verification keeps #720 open; state those pending actions explicitly.
