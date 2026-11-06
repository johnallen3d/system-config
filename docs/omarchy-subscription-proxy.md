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
- Personal Claude Code: personal proxy's Messages endpoint translated to Codex;
  no Claude subscription or Claude OAuth login is required.

CLIProxyAPI is pinned to source **8.0.23** and official Management Center to
**1.26.0**, independently of either host's nixpkgs lock. The official HTML asset
is hash-pinned in Nix, served from an immutable store path, and not auto-updated.
The official general model catalog is separately pinned to commit
`e63af9856bda19828dfe93a6fa0559a5ab32965c` and its content hash: 8.0.23's
embedded catalog predates Haiku 5.5. Both services load this immutable local
catalog; Codex-specific catalogs remain embedded. No mutable catalog URL or
automatic upstream catalog update is enabled. Activation explicitly PATCHes
only the pinned catalog path on already-active services and verifies runtime
publication: an atomic config-file write alone did not refresh the live registry.
This reload does not restart the services or agents.

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
4. Ask the operator to rebuild Omarchy (publishing the pinned routes) and verify live Go calls from
   both hosts before using the subagents. Pi uses `subscription-go/go/<model>`;
   no upstream key belongs in Pi. The model list is pinned in Nix (see below).

### Personal panel

Authenticate only **personal Codex**. Do not add work Claude, work Go, or any
work account to this instance.

If a browser on the Mac redirects to localhost and cannot connect, copy the
complete final callback URL into the official panel's callback field. The panel
submits it to Omarchy over Tailscale; no forwarding tunnel is needed. OAuth
sessions are short-lived; retry an expired flow from the panel. Do not paste
callbacks, provider keys, or management keys into agent chat/cards.

ALL upstream credentials, including Claude, are stored only on Omarchy. Native
Claude Code on either host uses its selected personal/work proxy's client key,
not independently managed upstream Claude OAuth credentials.

Go is API-key authentication, not OAuth. The endpoint is
`https://opencode.ai/zen/go/v1`, not pay-as-you-go Zen. Leave OpenCode Console's
optional **Use balance** setting off unless paid-credit fallback is wanted.
Only Go models served over Chat Completions are used; the pinned list is in
`go-models.json`. The gateway forwards Pi's `session_id` to `x-opencode-session`
and preserves its user agent. Do not remove those headers when editing the key.

Provider/employer policies still apply. Technical proxy OAuth support is not a
provider endorsement of subscription credential intermediation.

## Pinned Go model list

Tracked in [Fizzy #961](https://app.fizzy.do/6284043/cards/961), which replaced
the daily models.dev reconciler from #725.

The Go lineup is the checked-in file
`modules/home-manager/subscription-proxy/go-models.json`. Every entry is a Go
model served over plain OpenAI Chat Completions, so the gateway's single
**`opencode-go`** provider routes all of them; there are no Responses or
Messages groups. Nothing is fetched at runtime and there is no timer.

To add or retire a model, edit `go-models.json` (ID, display name, reasoning,
Pi input types, context window, output cap at most 32,768, nominal cost) and
rebuild. Check the model is listed by `https://opencode.ai/zen/go/v1/models`
and has no `npm` override in the `opencode-go` record of
`https://models.dev/api.json` (an override means Responses or Messages).
Costs shown in Pi are estimates, **not a promise of Go overage billing**.

On activation:

- Every host writes the list into work Pi's `subscription-go` provider.
- Omarchy runs `subscription-proxy sync-go` when the work gateway is active. It
  sets only the `opencode-go` provider's model list through the management API,
  preserving its key, endpoint and headers, and removes the retired
  `opencode-go-responses`/`opencode-go-messages` groups. It then waits for the
  gateway to publish every pinned `go/` model. If Go is disabled or has no key,
  it saves the list and skips the publish check. Do not save provider edits in
  the panel during a switch: v8 has no conditional-write API.

New Pi sessions load the updated models; use Pi's `/reload` or restart an
existing agent at your discretion.

## Select clients after provisioning and verification

Pi providers remain opt-in: once account identities and minimal live provider
calls have been verified, the operator selects Pi routes on BOTH client hosts.
Both personal and work Claude Code use their isolated proxies as **managed
defaults**, reapplied by Home Manager on both hosts; no separate Claude
activation command is needed.
This changes installed settings, never an already-running agent's environment.

```bash
subscription-proxy activate personal
subscription-proxy activate work
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

### Work Claude Code

`subscriptionProxy.workClaude.enable` defaults to true wherever proxy clients
are enabled (Mac and Omarchy). Activation writes only owned routing variables
and `modelPicker` in `~/.config/claude-gmatter/settings.json`:
`ANTHROPIC_BASE_URL` is the work server root, `ANTHROPIC_AUTH_TOKEN` is the work
proxy client key, and `ANTHROPIC_API_KEY` is cleared. Opus/Sonnet/Haiku/Fable
aliases are pinned to their work gateway IDs. Shared agent roles select **family
aliases**, not independent version IDs: Scout/Researcher use `haiku`, and
Planner/Worker/Reviewer use `opus`. These resolve through the work profile's
`ANTHROPIC_DEFAULT_*_MODEL` mappings, keeping role usage aligned with the same
curated gateway lineup. Personal roles use their own profile's alias defaults.
Do not pin an old/full model ID in agent frontmatter: that bypasses the managed
mapping (the undated `claude-haiku-4-5` is not advertised by the gateway even
though the dated `claude-haiku-4-5-20251001` is).

The installed Claude test queries the live work `/v1/models` catalog using only
the proxy client key and requires **all four alias targets and all six picker
IDs** to be advertised. This is a read-only availability check, not an inference
or quota guarantee. Model updates remain reviewed/pinned in
`subscription-proxy.nix`; missing IDs fail verification instead of guessing a
replacement or falling back to another provider. Per-invocation model overrides
still take precedence over role aliases. Restart existing work Claude sessions
when convenient after changing agent definitions; they may retain loaded roles.

The saved default model is
preserved; the existing `opus` selection resolves to Opus 5.5.

The `/model` picker has six labeled entries, in this order:

| Label | Exact gateway model ID |
| --- | --- |
| Claude Haiku 5.5 | `claude-haiku-5-5` |
| Claude Opus 5.5 | `claude-opus-5-5` |
| Claude Fable 5.1 | `claude-fable-5-1` |
| Codex 6 Luna | `gpt-6-luna` |
| Codex 6.1 Sol | `gpt-6.1-sol` |
| Codex 6 Astra | `gpt-6-astra` |

Use plain `claude` in the shared Amfaro context and `/model` to switch; explicit
`claude --model <id>` works too. Model selection does not change gateways or
accounts. The curated picker replaces the built-in lineup, rather than relying
on discovery that filters out non-Claude IDs. Sonnet 5.5 remains a pinned helper
alias for existing subagents, not an extra picker entry. Omarchy's Nix-managed
Claude is pinned to official 2.1.295 because Haiku 5.5 needs >=2.1.293; Mac's
existing native Claude must also meet that minimum.

Codex through Claude Code uses the gateway's Messages-to-Responses translation.
Anthropic does not officially support non-Claude backends through gateways;
live Claude Code streaming/tool tests are required, not just Pi inference.
Tailscale and Omarchy must be available: there is no silent direct-account fallback.
Client-settings activation requires the already-provisioned proxy client key
but makes no inference/readiness calls, so offline client activation does not
revert routing. Server activation separately verifies its live catalog reload.

Permissions/hooks/plugins/sessions and unrelated settings are preserved. No
upstream example's permission-bypass settings are copied. Personal Claude has its own Codex-only routing described below. Existing native
auth files remain untouched, not copied or deleted.
The legacy `activate work --claude` command remains available but is unnecessary
for managed clients.

Private `selected.json` records host-local selections for future Home Manager
activation. Configuration/credential runtime data never belongs in Git.

### Personal Claude Code without a Claude subscription

Tracked in [Fizzy #764](https://app.fizzy.do/6284043/cards/764).
`subscriptionProxy.personalClaude.enable` defaults true wherever proxy clients
are enabled (Mac and Omarchy). Home Manager manages only owned routing variables
and the model picker in `~/.config/claude-personal/settings.json`, preserving
permissions, hooks, plugins, sessions and unrelated settings. The personal
client key authenticates only against port **8317**; work keys/accounts are never
used. `ANTHROPIC_API_KEY` is cleared, and upstream Codex OAuth credentials stay on
Omarchy. No Claude account/login or Claude subscription is needed for inference.

Use plain `claude` outside the Amfaro work context. The default is **Codex 6 Luna**
(`gpt-6-luna`); `/model` offers Luna, **Codex 6.1 Sol** (`gpt-6.1-sol`) and
**Codex 6 Astra** (`gpt-6-astra`). Explicit `claude --model <id>` also works.
`ANTHROPIC_DEFAULT_MODEL` supplies Luna only as a fallback; a choice saved with
`/model` takes precedence on new sessions. Activation removes the old managed
`ANTHROPIC_MODEL` forcing Luna only if it still matches the previous managed
value, preserving operator changes and the saved `model` field.
`ANTHROPIC_SMALL_FAST_MODEL` uses Luna; `sonnet`/`haiku` aliases use Luna, `opus`
uses Sol, and `fable` uses Astra, including managed agent roles. These are
compatibility aliases, not calls to Claude models. This does not change personal
Pi selection or work Claude routing.

Each personal picker entry sets `behavesAs = "claude-sonnet-4-6"` for Claude Code's
client-side capability catalog. The displayed label and outgoing model ID remain
Codex. This removes the unknown-model startup warning and retains a conservative
**200K** context/compaction window, below the pinned gateway Codex catalog's
**272K** window. No 1M window is claimed, and neither context enforcement nor
compaction is disabled. Client effort/capability defaults come from this
compatibility profile, not a declaration that Codex is a Claude model. See the
[official picker reference](https://code.claude.com/docs/en/settings-reference#fields-for-modelpicker)
and [fallback-default precedence](https://code.claude.com/docs/en/model-config#set-a-default-model-for-new-sessions).

CLIProxyAPI translates Claude Code's Messages/streaming/tools to Codex Responses.
This is not an Anthropic-supported non-Claude backend; compatibility and
provider policies can change. It uses the personal Codex account's access/quota,
not a free Claude entitlement. Tailscale and the Omarchy gateway must be online;
there is no silent work-account or native-Claude fallback. Start a new personal
Claude session to load routing; active agents are never restarted automatically.
After routing changes, inspect the selected model in a new personal session on
each host and compare its alias with the gateway catalog. Live streaming/tool or
subagent verification makes real model calls and must be explicitly scoped; it
is not an ordinary deployment gate. Never print credentials or raw transcripts.

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
# For Claude rollback, first disable the corresponding workClaude/personalClaude
# option and apply on BOTH hosts, then restore each host's owned routing/picker:
subscription-proxy deactivate work --claude
subscription-proxy deactivate personal --claude
```

This restores only owned client settings from a private host-local rollback
record, preserving unrelated changes. While managed Claude routing remains
enabled, the next Home Manager activation restores the proxy and curated picker.
Restart affected agents when convenient.
Central logins are not revoked. Revoke upstream tokens separately when
removing/decommissioning the gateway.

Tests:

- `subscription-proxy.py`: temporary-home private state/client/UI-launch tests,
  using Python with PyYAML (the manager's Nix-provided interpreter).
- `subscription-proxy-installed.py`: installed Tailscale/auth/state checks and
  exact official-panel content hash; use `--server` on Omarchy.
- `subscription-proxy-claude.py`: run with explicit work `mise exec` on each
  host for work, or `--profile personal` in personal context. Verifies installed
  profiles, client auth, source/installed role aliases, all configured alias
  targets and picker IDs against the live gateway catalog, and minimum Claude
  version (network metadata only, no inference by default).
  Personal `--live-default` also checks actual routing without a `--model`
  override, respecting the saved picker choice. Personal live checks reject the
  unknown-catalog warning and require the safe 200K client window; installed
  checks verify that the central Codex catalog supports at least that window.
  `--live-subagent scout --live-subagent researcher --live-subagent planner`
  makes bounded actual Agent dispatches, checks child Read calls and exact
  managed model usage without overriding the child's model. The parent uses a
  different model family so child usage cannot be mistaken for parent usage.
  Each dispatch has a timeout and $1 budget cap; it persists no session.
  `--live` tests each picker model through actual Claude Code
  streaming and a read-only tool, verifies exact model usage, suppresses raw
  transcripts/errors, and disables session persistence; `--model <id>` limits
  the live checks. Each call has a timeout and $1 budget cap.
- `subscription-proxy-protocol.py`: isolated real proxy against a loopback mock,
  testing the panel's v8 configuration/OAuth API and Go routing/session headers.
- `subscription-proxy-pi.mjs`: each host's actual Pi runtime model loader/key
  resolution, mock tool streaming, and conversation header emission.

Live Codex/Claude/Go calls and effective client/no-fallback checks on BOTH hosts
are still required after approvals. Any pending login, host deployment, or
verification keeps #720 open; state those pending actions explicitly.
