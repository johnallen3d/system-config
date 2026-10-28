# Pi Pocket / Pi Durable on Omarchy

John's production personal assistant. It began as the [#796](https://app.fizzy.do/6284043/cards/796)
trial and replaced Hermes in [#906](https://app.fizzy.do/6284043/cards/906);
the Hermes Telegram bot is gone, but the morning brief still sends its summary
to Telegram (see below). Mac configuration is unchanged. `hosts/omarchy.nix`
alone enables `omarchy-pi-pocket.nix` (`piPocket.enable`).

Skills, prompts, Pocket extensions and the tasks they call belong to the notes
vault (`~/notes/.pi`, `~/notes/.pocket`, `~/notes/.mise/tasks`), not this
repository. This repository owns only the runtime: sandbox, tools on PATH,
credential locations, the service, and schedules.

## Open it

On a Mac connected to the tailnet, deliberately retrieve the private owner URL
and open it without printing its bearer token into logs or a chat:

```bash
open "$(ssh johna@omarchy '~/.local/bin/pi-pocket-login')"
```

On Omarchy, `~/.local/bin/pi-pocket-login` prints that URL when explicitly
requested. Treat it as a password; do not paste it into Fizzy. The ordinary
address is `http://omarchy:8796` (or its Tailscale IPv4 address). The service binds
only the Tailscale IPv4 address, not wildcard, LAN, or loopback. Port 8787 already
belongs to another service. Existing Tailscale Serve mappings are unchanged.
HTTP is carried inside the encrypted tailnet; this does **not** provide an HTTPS
browser origin. Browser features requiring a secure origin, including some PWA,
push and microphone functions, are not available.

Pocket uses **subscription-codex**, the existing personal Codex proxy on
Omarchy port 8317, through OpenAI Responses. In the session's model picker choose
**Codex 6 Luna**, **Codex 6.1 Sol**, or **Codex 6 Astra** (personal proxy). Use
**Providers → Refresh models** if the browser has an older empty list. The app's
saved default is **Codex 6 Luna**, thinking off, for new sessions; the original
starter session uses it too. Model/thinking choices remain user-changeable app
state, not forced Nix settings. No separate Codex browser login or OpenAI API
billing is required. Subscription quota and
provider terms still apply; there is no work-account or direct-provider fallback.

Home Manager owns the nonsecret `models.json` in Pocket's isolated profile.
Only the personal proxy **client** key is deliberately provisioned into the
profile's private `proxy-client-key` file (0600); a credential command reads it
at request time. Upstream OAuth, management/work keys, production auth files and
sessions remain outside Pocket. Trusted Pocket tools can access this client
key, as they can Pocket's owner token. It grants personal proxy access and is
not a separately scoped gateway credential. If the personal client key rotates,
reprovision this one private file deliberately on Omarchy; do not copy the proxy's
whole credential store or another Pi profile.

## State and boundaries

- App: Pi Pocket **0.17.0**, revision
  `26542deded0123d6b217828ed2f71f566d9a7a19`; compatible Pi packages **1.1.0**,
  with upstream's lockfile. Do not upgrade Durable alone.
- Service: `systemctl --user status pi-pocket.service`.
- Installed non-secret manifest: `~/.config/pi-pocket/deployment.json`.
- Host private home: `~/.local/state/pi-pocket/home`, mode 0700.
- Inside the sandbox: HOME `/home/pi-pocket`,
  `PI_CODING_AGENT_DIR=/home/pi-pocket/.config/pi-pocket`, app data
  `/home/pi-pocket/.pi-pocket`. The default workspace is **`~/notes`**
  (`/home/pi-pocket/notes`), a **read/write bind of the real `/home/johna/notes`**,
  explicitly authorized by John for the whole project. No vault copy or
  synchronization is involved.
  The existing host auto-commit process is unchanged; it is not an exactly-once
  or concurrency guarantee. Continue using the existing locked vault writers.
  For temporary generated
  files, `/home/pi-pocket/scratch` remains writable. From a normal Omarchy shell,
  use `cd ~/notes`; do not use the sandbox's `/home/pi-pocket/...` paths there.
- Pocket's proxy client credential lives only in its private writable profile;
  upstream subscription credentials remain in the central gateway's private store.
  The interactive agent's inherited `PI_CODING_AGENT_DIR` and `CLAUDE_CONFIG_DIR`
  are not changed.
- Bubblewrap starts from an empty root: only the read-only Nix store, public
  resolver/hosts files, private `/proc`, minimal `/dev`, private `/tmp`, shell
  links, the writable Pocket home, and the read/write notes project are mounted.
  Other agents' state and profiles, user bus, SSH sockets, and host processes
  remain absent. All tools and extensions can now modify the entire notes project,
  including its scripts and command adapters; this is not a food-only boundary.
  App source and the Nix store remain immutable.
- **Not a network sandbox**: model/internet traffic is needed, and host/LAN
  network services remain reachable. It is not a separate OS account, VM, or hostile multi-tenant boundary.
- Anyone who can steer can access Pocket's own tokens and files. Invite only
  trusted people. Provision only Pocket's own credentials into its writable home.
- Browser and Cloudflare tunnel binaries are not included. Browser, gallery,
  goals, guard, memory, PiP, schedules, subagents, triggers, and agent teams start
  off. Those UI
  choices are writable app state, not hard security controls.

The upstream SQLite backend uses WAL and synchronous=NORMAL: process recovery is
not an exactly-once guarantee for external effects or protection against every
power-loss window. The service holds a host-side `flock` in addition to the app's
PID lock, since PID namespaces cannot arbitrate one another. Never open the live
SQLite file with a second Harness for inspection; use the running app's API/UI.

## Search

`/search food milk` and `/search food --nutrition "greek yogurt"` run the
existing notes `mise run common-food -- search …` task directly and display its
text as a session card; no model request is made. The adapter belongs to notes at
`.pocket/extensions/notes-search.ts`, linked into Pocket's drop-ins and enabled
as **notes-search**. Nix supplies mise, usage, yq and column. A narrowly scoped
package patch permits exactly `/search` from that module (and `/food` from its
own module); other extension names retain upstream's hyphen requirement. Search
itself remains read-only. Invalid input,
a failed task or a ten-second timeout is reported instead of sent to the model.

## Food logging

`/food lunch 2 eggs and 250 ml milk` calls the existing notes `mise run log-food`
helper and returns its brief result as a session card. Unlike `/search`, this
uses a model: **subscription-codex/gpt-6-luna**, thinking medium, in an ephemeral
helper session with Pocket's existing `PI_CODING_AGENT_DIR`. No credentials or
sessions are copied from another profile. The adapter is notes-owned at
`.pocket/extensions/notes-food.ts`, enabled as **notes-food**. Its command is
owner-only because it writes shared nutrition records, not merely the conversation.
Nix permits exactly `/food` from that file alongside the existing `/search`
exception; other command names retain upstream's restrictions. While this exact
command is enabled, Pocket omits the same-name CLI prompt template from its
catalog so the browser routes `/food` directly to the helper command. Other
templates keep their normal precedence; disabling notes-food restores the CLI
template in Pocket. `.pi/prompts/food.md` itself is unchanged.

The helper resolves local reusable foods/recipes, preserves quantities and dates,
uses the existing daily-note writer (template hydration, locking, totals and
readback), and asks for clarification when needed. Bare milk means Kirkland
ultra-filtered 2%. No web research or reusable-food edits are added to this path.
Include the complete entry again when supplying a clarification: helper sessions
are ephemeral. Label-photo capture and food correction commands are not part of
this text-command integration.

Nix supplies pinned Pi, Python/PyYAML, vlt and an offline food-pick runner. Runtime
`FOOD_LOG_PROVIDER` / `FOOD_LOG_MODEL` select the existing personal proxy; the
shared task retains its ordinary CLI defaults elsewhere. `VAULT_NAME` is the
absolute sandbox vault path, so use `vlt vault="$VAULT_NAME"`, not a host Obsidian
registry name.

Use **Running now** to stop a food command. It has a five-minute process-group
limit. Stopping, failure or restart does not undo a completed write. Pocket
request IDs deduplicate the same command submission; interrupted handlers are
not automatically replayed. Inspect the daily note before an explicit retry;
this is not an exactly-once external-effects guarantee.

## Google (gog)

- `jallen7usa@gmail.com` (`--client personal`): **Calendar read/write, Gmail
  read-only** (`--gmail-scope readonly`).
- `john.allen@gmatter.co` (default client): **Calendar and Gmail read-only**
  (`--readonly`), which also lets the morning brief include the work calendar.

- Nix puts the pinned `gog` from `packages/vault-tools.nix` on the sandbox PATH
  and sets `GOG_HOME=/home/pi-pocket/.config/gogcli` (host:
  `~/.local/state/pi-pocket/home/.config/gogcli`, mode 0700).
- Activation generates a local file-keyring password there once
  (`keyring-password`); the sandbox loads it as `GOG_KEYRING_PASSWORD`.
- `GOG_ENABLE_COMMANDS=auth,config,calendar,gmail` and `GOG_GMAIL_NO_SEND=1`
  limit the CLI. Untrusted-content wrapping is per command (`--wrap-untrusted`),
  not global, so task output such as the brief's calendar stays clean. The real Gmail boundary is the OAuth
  grant: Google rejects changes outside each token's scopes. Anyone who can steer Pocket can use these tokens within those
  scopes. Pocket's Nix-managed `AGENTS.md` states this runtime boundary; the
  generic `google-workspace` skill lives in notes.
- To authorize another account, run inside the sandbox
  (`~/.local/bin/pi-pocket-sandbox gog auth add ACCOUNT [--client personal]
  --services gmail,calendar --readonly --remote --step 1`, or `--gmail-scope
  readonly` instead of `--readonly` to keep Calendar writable), approve
  the printed URL, then finish with `--step 2 --auth-url 'REDIRECT_URL'` and check
  `gog auth list --check --json`. The OAuth client files already live in
  Pocket's `gogcli/data`.

## Morning brief

`pi-pocket-morning-brief.timer` runs daily at 05:00 (`Persistent=true`). Its
oneshot service runs the notes `mise run morning-brief` inside the Pocket sandbox:
it updates today's daily note (weather and personal and work calendars) and
sends the summary to John through the notes `send-telegram` task. Failures land
in `journalctl --user -u pi-pocket-morning-brief.service`.

- `send-telegram` reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from Doppler
  `notes/pocket`, which holds only those two secrets. Nix puts `doppler` on the
  sandbox PATH and the sandbox loads `DOPPLER_TOKEN` from
  `/home/pi-pocket/.config/doppler/service-token` when readable (host:
  `~/.local/state/pi-pocket/home/.config/doppler/service-token`, 0600, directory
  0700). That read-only service token is provisioned out of band, not by Nix;
  without it the brief cannot send. `DOPPLER_CONFIG_DIR` is the same directory
  and version checks are off.
- Boundary: the token is in Pocket's environment, so anyone who can steer
  Pocket can read the bot token and chat ID and message that chat as the bot.
  It grants nothing else in Doppler.

The brief's lock directory is under the sandbox's private `/tmp`, so it
does not exclude a concurrent Pocket write to the same daily note.

## Operations

Routine journal output redacts startup owner URLs. Full private transcripts stay
in app state; do not paste them or provider diagnostics into routine logs.
Use `journalctl --user -u pi-pocket.service` deliberately when needed.

After relevant changes, inspect `systemctl --user status pi-pocket.service`,
its installed sandbox/listener settings, and the browser page. An unauthenticated
request to `/api/sessions` must return 401. Keep real-vault bind identity and
writable state intact; do not open the live database or change notes just to
verify a deployment. There is no repository-owned Pocket test suite.

The service sets `X-RestartIfChanged=false` to preserve active conversations:
after a runtime change, restart `pi-pocket.service` deliberately while it is
idle. Deploy with the normal coordinator (`system-config-deploy`); do not run a
macOS rebuild on Omarchy.

To pause Pocket: `systemctl --user stop pi-pocket.service`. Disabling
`piPocket.enable` and activating Home Manager removes its service, timer and
launchers, not writable data. Do not delete data, rotate tokens, or roll back a
database schema without an explicit decision and compatible private backup.

Hermes's former state remains on disk, unused, under
`~/.local/state/hermes-native`, `~/.local/share/hermes-native`,
`~/.config/hermes-native` and `~/.cache/hermes-native`. Deleting it is a
separate decision.
