# Claude Code startup-context audit

[Fizzy #726](https://app.fizzy.do/6284043/cards/726) audits John's observation of
33–100k initial tokens on Omarchy versus about 15k on Mac. The persistent,
reviewed context-policy change and its narrower capability tradeoffs are recorded in
[#731](https://app.fizzy.do/6284043/cards/731).

## Result

The current absolute-token mismatch is real. **Claude's native tool schemas
are the largest isolated cause**, not the shared work instructions or
agent-kit MCP. The Mac already has a substantial **user-owned** slimming policy
that Omarchy lacks. It is not declared by the shared Nix modules.

A temporary, context-only overlay of that policy brought Omarchy to slightly
below the Mac's baseline. The overlay was not installed. No credentials,
settings, models, plugins, or running agents were replaced or restarted.

The historical ~100k requests are also real, but are not an apples-to-apples
comparison with today's ~15k Mac request. Their additional payload has not been
fully isolated; see the historical evidence below.

## Controlled measurements (2026-10-09)

Both hosts used:

- Their actual work Claude and Pi profiles, selected through Amfaro `mise exec`.
- Claude Code **2.1.295**, model **claude-haiku-5-5**, and an effective **1M**
  context window, verified from actual inference usage rather than a label.
- The same disposable project content and identical one-line prompt beneath
  `~/dev/src/amfaro`, with no repository history or resume.
- The installed `agent-kit@amfaro` **0.59.0**, Git revision
  `6a01c99cd7baf2b89ddd6c924de42f240734849b`.
- Normal installed settings, native tools and MCP discovery; no tool calls,
  no `--bare`, no skill/tool suppression except in explicit overlay experiments.
- A fresh `--print` session with `--no-session-persistence`. Both hosts used
  the managed work subscription proxy, not a temporary native-login fallback.
- `CLAUDE_CODE_DISABLE_1M_CONTEXT=0` and experimental betas disabled.

The Mac's normal executable was 2.1.296. Its existing host-local 2.1.295
binary was selected for the controlled comparison; no binary was transferred.

| Host / temporary policy | Initial API input tokens | Fraction of 1M |
| --- | ---: | ---: |
| Mac, existing slim work settings | 13,940 | 1.3940% |
| Omarchy, existing work settings | 35,443 | 3.5443% |
| Omarchy, Mac's tool-name denies only | 16,126 | 1.6126% |
| Omarchy, Mac's context-only policy | 13,412 | 1.3412% |

The full overlay removes **22,031 tokens (62.2%)** from Omarchy's first request.
The deny-only experiment isolates **19,317 tokens** of that reduction without
changing bundled-skill or memory settings. Small differences of a few tokens
between repetitions are expected from temporary paths and dynamic context.

Initial input is **input + cache creation + cache read**, not only uncached
`input_tokens`. Cached tokens still occupy context. Output/thinking tokens and
subsequent requests are not added to this baseline.

Fixture SHA-256:
`9691a8b5377deb0cc34a7e383ffdaa3a5b26947194344b44362b3161f4d79dc2`.
Prompt SHA-256:
`8ea0e73dbbad127019114b1d9fe894cd97dd5ec662242421c7c4692c930a0ac3`.

### Independent interactive `/context` breakdown

Fresh interactive sessions used the same fixture, runtime, model and 1M window.
Only `/context` was submitted, not a model prompt. The command reports **local
estimates**; these are not the exact API counts above. Interactive and print
mode can also load different tool sets. Keep the two measures separate.

| Estimated category | Mac | Omarchy | Omarchy, temporary full policy |
| --- | ---: | ---: | ---: |
| Total occupied context | 10.6k | 52.8k | 10.3k |
| System prompt | 2.2k | 3k | 2.2k |
| Native system tools | **4.2k** | **44.2k** | **4.4k** |
| MCP tools | 550 | 81 | 81 |
| MCP server instructions | 184 | 184 | 184 |
| Custom agents | 380 | 380 | 380 |
| Memory/instruction files | 1k | 1.1k | 1.1k |
| Skills | 1.6k | 3.5k | 1.5k |
| Messages (including hook context) | 372 | 372 | 372 |

The Mac reserves a 3k compact buffer; Omarchy reserves a 33k autocompact buffer.
**A reserved buffer is not an initial request payload.** Disabling autocompact
just to shrink a graph is not the proposed fix.

## Effective installed differences

- **Profiles:** both effective work variables were correct. Personal profiles
  were not used or modified. Omarchy's active Home Manager source is the
  non-Git `~/dev/src/system-config-amfaro` snapshot; its inspected instructions
  and launcher match the documented standalone-HM setup, not a Mac deployment.
- **Runtime:** normal Mac 2.1.296 versus Nix-pinned Omarchy 2.1.295. Matching
  2.1.295 still reproduces the gap, so this one-release difference is not its
  explanation.
- **Saved model:** Mac `haiku`; Omarchy `gpt-6-luna`. Explicit model selection
  in the experiment prevents saved choices from confounding it. Earlier
  unnormalized Haiku/Opus print probes found about 14.0k/12.9k on Mac versus
  35.4k/34.3k on Omarchy respectively.
- **Window environment:** the Mac session inherited
  `CLAUDE_CODE_DISABLE_1M_CONTEXT=1`; Omarchy's launcher forces `0`. Unnormalized
  Mac inference reported 200k and Omarchy reported 1M. This affects percentage
  and buffer denominators, **not the confirmed absolute-input mismatch**.
- **Context policy:** Mac has 32 tool-name denies, `disableBundledSkills=true`,
  nine skill overrides set to `off`, and `autoMemoryEnabled=false`. These are
  absent on Omarchy. Mac also has user-owned `autoCompactEnabled=false` and
  `channelsEnabled=false`; those two flags were **not** copied in the temporary
  inference overlay.
- **Tools:** the print-mode Mac advertises eight core tools plus two agent-kit
  gateway tools and three Headroom tools. Omarchy advertises 24 native tools
  plus the same two agent-kit gateway tools. The temporary full policy leaves
  the same eight core native tools and two gateway tools on Omarchy.
- **Plugins:** one enabled agent-kit installation at the same version/revision
  on each host. Mac also has a disabled old `claude-hud`; it is not loaded in
  the controlled runtime. Disk caches and synced-skill directories alone are
  not evidence of loaded context. Runtime discovery was checked separately.
- **MCP:** agent-kit is connected on both hosts and exposes only `find_tools`
  and `call_tool`. Mac additionally has the local Headroom MCP; Omarchy's lack
  of that Mac-local endpoint is intentional. Headroom is not automatically
  compressing the entire Claude HTTP request; both Claude routes are the work
  subscription proxy. The Pi `pi-headroom` extension is a separate integration.
- **Instructions:** work-global `CLAUDE.md` is 2,735 bytes on Mac and 2,978 on
  Omarchy; the Linux-only suffix is intentional. The fixture has only its small
  identical `CLAUDE.md`; no ancestor `CLAUDE.md` was found in the inspected
  home/dev/src/Amfaro chain. Custom agents and ELI5 style are shared.
- **Hooks:** both have the shared Herdr session-start hook and plugin hooks.
  Mac also has Supacode terminal-state/notification hooks; these suppress
  stdout and are guarded by the Supacode environment. Audit subprocesses clear
  Herdr/Supacode pane variables rather than impersonating an active agent.
  The equal 372-token `/context` message estimate is consistent with shared
  short agent-kit startup guidance, not a huge hook injection.
- **Overrides:** Mac has parent Amfaro permission settings; Omarchy has none.
  Both have channel-related remote settings and policy-limits files. The large
  difference is reproduced in the isolated fixture without project-specific
  source instructions. No unrelated auth/runtime values were dumped or copied.

## Historical ~100k evidence and remaining uncertainty

Omarchy's recorded single-reply session `19a0d4c9-c698-4b5e-8cde-53bef30ca192`
used **2.1.289 / claude-opus-5-5** and sent **104,781 initial input tokens**
(10,815 uncached + 93,966 cache creation), with a small initial user message and
no tool calls. Other 2.1.289 sessions start around 103–105k. A recent Mac
single-reply session used Haiku and sent **14,759** initial input tokens.

Some historical Omarchy sessions used `mcp__claude_ai_Slack__...` tools.
Today's fresh proxy-backed sessions explicitly report that claude.ai connectors
and sync are disabled because proxy authentication takes precedence. Those
connectors and older launch conditions are therefore a plausible additional
source of historical payload, **not a measured attribution of all ~70k extra**.

A control using Omarchy's still-installed 2.1.289 binary, current work proxy and
current untrimmed settings sent **33,926** initial tokens for Opus with a 1M
window. Thus **version alone does not reproduce ~100k either**. Recreating the
old auth/connector state would require a separate, explicitly authorized probe;
this audit did not unset proxy auth, copy OAuth credentials, or replay old
sessions. Existing sessions retain their original launch-time context.

## Reproduction

`tests/claude-context-audit.py` defaults to a sanitized installed-state inventory.
It asserts **both** work profile variables, and never emits credentials,
transcript text, provider error bodies, or executable hook bodies.

```bash
# Offline parser, cache accounting, and overlay-isolation regression tests.
mise exec -- python3 tests/claude-context-audit.py --self-test

# Installed inventory; absolute path is needed because mise -C changes cwd.
mise -C ~/dev/src/amfaro exec -- python3 "$PWD/tests/claude-context-audit.py"

# One explicit, bounded model turn through the selected work proxy.
mise -C ~/dev/src/amfaro exec -- python3 "$PWD/tests/claude-context-audit.py" --live

# Mac: choose its existing matching binary and retain the actual work profile.
mise -C ~/dev/src/amfaro exec -- python3 "$PWD/tests/claude-context-audit.py" \
  --live --claude "$HOME/.local/share/claude/versions/2.1.295"
```

On Omarchy run through `ssh johna@omarchy 'bash -s'`, using the absolute script
path in its inspected snapshot. The inference subprocess uses `/dev/null` stdin,
so it cannot consume the remaining SSH Bash script. `--model claude-opus-5-5`
selects the other tested Claude model. `--overlay /tmp/context-policy.json` uses
only a temporary CLI overlay; the parser rejects auth, hooks, and permission
bypass settings. Each live probe has a $2 ceiling and a 240-second timeout.

For an interactive check, start a **new isolated** work session with the matched
model/window and use `/context`. `--no-session-persistence` is print-only; do not
pass it to interactive Claude. Do not reuse or restart an active agent for this.

## Recommended persistent change

Review and declare a **work-only** slim policy in shared Home Manager rather
than copying a whole Mac `settings.json`. The deny-only experiment already gets
Omarchy to ~16k without disabling all bundled skills. The full existing Mac
policy is more aggressive: it also denies `AskUserQuestion`, plan/worktree
helpers, notebook editing, messaging, scheduling/workflow tools, artifact tools,
and selected claude.ai connectors. Review those capability tradeoffs first.

The audit itself made no persistent changes. After rejecting an initial narrower
implementation, John explicitly requested **Mac-equivalent context on both hosts**.
The shared policy below implements that request, including Mac’s tool exclusions.

## Reviewed work-context policy (#731)

John explicitly requested replication of the full Mac work-context footprint on
Omarchy, targeting **approximately 14k initial input tokens on both hosts**.
An initial conservative policy only reduced Omarchy from 35,440 to 31,151 tokens;
John rejected that compromise. It is superseded, not the completed outcome.

### Mac-equivalent policy

`modules/home-manager/claude-work-context/policy.json` was extracted from Mac’s
work settings and is shared through `agent-projects.nix` on both hosts:

- The **31 tool-name denies**, including Mac’s exclusions for question/plan/worktree
  helpers, notebooks, scheduling, messaging, workflow tools, artifacts, and the
  selected claude.ai connectors. Core coding tools and the agent-kit gateway remain.
- All **10 named skill overrides** from Mac, including the documentation skill.
- `disableBundledSkills = true`, `autoMemoryEnabled = false`,
  `autoCompactEnabled = false`, and `channelsEnabled = false`.

These exclusions are intentional and explicitly approved by John’s request to
replicate Mac, rather than a capability-preserving redesign. No saved model,
context-window/beta environment, routing, hooks, credentials, personal settings,
or memory files are copied or changed. Existing host restrictions are retained.
Other host-local integrations are not credential-cloned: Mac still has its
Headroom and Supacode resources; the native-tool footprint matches on both hosts.

Home Manager installs a readable `~/.config/claude-gmatter/work-context-policy.json`
and runs an atomic work-only merge after the profile-default/UI writers. It
appends missing denies without deleting existing rules, applies the named skill
overrides and four owned flags, and leaves every other work field alone. Settings
stay private (0600), writable, and host-local. Invalid settings and unexpected
symlinks fail without replacement. Removing a declaration or rolling back a
Home Manager generation does not silently revoke runtime restrictions; undoing
one requires explicit review of whether it was already host-owned.

### Deployment and preservation

Both hosts were independently activated and verified with the **full** policy.
Mac used `mise update-system --switch-only`; Omarchy used the documented standalone
Home Manager `path:.` build/activation from its inspected snapshot. Only intended
files were transferred. Each host retained its original flake.lock; Omarchy’s
older inputs were not overwritten. No active agents or Herdr servers restarted.

Installed checks verify both profile variables, policy/flags, private writable
settings, and before/after hashes for all **unowned** work fields, existing denies,
personal settings, and profile credentials. The four context flags and ten named
skill overrides are now deliberately managed. Mac retained `haiku`; Omarchy
retained `gpt-6-luna`. Saved window preferences/routing/hooks are unchanged.

### Fresh measurements: approximately 14k achieved

Matched tests used the same fixture/prompt hashes, work proxy,
**Claude Code 2.1.295 / claude-haiku-5-5 / actual 1M window**, one bounded model
turn, no tool calls, and no persisted session. Counts include cache categories.

| Host | Full-policy before | Full-policy after |
| --- | ---: | ---: |
| Mac, existing footprint | 13,940 | **13,938** |
| Omarchy, replacing the rejected conservative policy | 31,154 | **13,410** |

Compared with the original untrimmed Omarchy baseline of **35,440**, the final
**13,410** footprint removes **22,030 tokens (62.2%)**. Its small difference from
Mac reflects remaining host-local integrations/instructions, not native tools.

The plain installed launchers were also live-tested: **Mac 2.1.296: 14,038 tokens**;
**Omarchy 2.1.295: 13,410 tokens**. The table uses 2.1.295 for a matched-version
comparison; neither binary was updated by this change.

Both hosts advertise exactly the same **eight native tools**: `Task`, `Bash`,
`Edit`, `Read`, `Skill`, `WebFetch`, `WebSearch`, and `Write`. Both discover the
connected agent-kit `find_tools`/`call_tool` gateway and matching agent-kit coding
skills. Mac additionally advertises its three existing Headroom tools. The ten
excluded skills are absent from both live inventories. Installed settings verify
all denies, including those for interactive-only tools/connectors not advertised
in proxy-backed print mode; that is not a native-login connector execution test.

### Repeatable gates

```bash
# Offline merging, Mac capability boundary, safety, and ~14k regression checks.
mise exec -- python3 tests/claude-work-context.py
mise exec -- python3 tests/claude-context-audit.py --self-test

# Immediately before activation; stores private hashes, not values.
mise -C ~/dev/src/amfaro exec -- python3 "$PWD/tests/claude-work-context.py" \
  --record-before /tmp/claude-work-before.json

# Explicit live inference through the installed launcher.
mise -C ~/dev/src/amfaro exec -- python3 "$PWD/tests/claude-context-audit.py" \
  --live > /tmp/claude-work-live.json

# Installed state, preservation, native-tool equality, and 12k–15k target gate.
mise -C ~/dev/src/amfaro exec -- python3 "$PWD/tests/claude-work-context.py" \
  --installed --before /tmp/claude-work-before.json \
  --live-report /tmp/claude-work-live.json
```

Use absolute script paths on Omarchy because `mise -C` changes the working
directory. Start **new work Claude sessions on both hosts** to load the full
policy; existing agents keep launch-time tools/settings and were left running.
