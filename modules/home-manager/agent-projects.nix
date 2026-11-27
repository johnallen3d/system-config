{
  config,
  lib,
  pkgs,
  ...
}: let
  amfaroConfig = "${config.home.homeDirectory}/dev/src/amfaro/mise.toml";
  # Personal projects whose tracker is a Fizzy board get a .fizzy.yaml.
  # Omit api_url (https://app.fizzy.do is the default/profile URL): fizzy CLI 4.x
  # warns on stderr whenever a repo .fizzy.yaml sets api_url without being trusted.
  fizzyProjects = lib.concatMap (p: let
    m = builtins.match "fizzy:([^/]+)/(.+)" (p.tracker or "");
  in
    lib.optional (m != null) {
      dir = config.home.homeDirectory + lib.removePrefix "~" p.path;
      file = pkgs.writeText "fizzy.yaml" ''
        account: "${builtins.elemAt m 0}"
        board: ${builtins.elemAt m 1}
      '';
    })
  (builtins.fromTOML (builtins.readFile ./agent-projects/projects.toml)).personal;
  attributionInstructions = builtins.readFile ./agent-projects/attribution-instructions.md;
  delegationInstructions = builtins.readFile ./agent-projects/delegation-instructions.md;
  taskScopeInstructions = builtins.readFile ./agent-projects/task-scope-instructions.md;
  deploymentInstructions = builtins.readFile ./agent-projects/deployment-instructions.md;
  htmlReportInstructions = builtins.readFile ./agent-projects/html-report-instructions.md;
  omarchyInstructions = lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''

    ## Arch/Omarchy

    This is standalone Home Manager on Arch/Omarchy, not macOS or NixOS.
    Never run macOS rebuild tasks here or change Omarchy shell/desktop settings.
    See docs/omarchy-agents.md in system-config for application and authentication.
    Omarchy, Miller, and Drummer reach each other over the tailnet as `johna@<host>`
    without prompts; use `rsync`/`scp`/`ssh` directly for cross-host copies.
  '';
  # Always-on rules only; procedures live in skills and the /wrap command.
  personalInstructions =
    ''
      # Personal agent instructions

      - Always respond in English. The user's name is John Allen.
      - Respect `PI_CODING_AGENT_DIR` and `CLAUDE_CONFIG_DIR`; keep profiles,
        credentials, and sessions separate.

      ## Scope

      - John's requested outcome is the scope boundary; workflow rules never
        authorize extra deliverables. Ask before adding optional edits, worktrees,
        docs, tests, deployment, or investigation.
      - In a repository that tracks work in Fizzy, if no card covers the task,
        create one as soon as the task is understood, before implementation,
        and link it with `switchyard link REF` (`switchyard-links` skill).
        Card creation and linking are tracking bookkeeping, not extra
        deliverables; do them without asking. When John asks for a sub-agent,
        delegate first.
      - A direct operation on a user-owned file outside a repository needs no
        repository edits or worktree; a Nix-managed file needs its declarative
        source and deployment workflow.
      - Use the smallest verification that proves the result. A failed optional
        check is not a blocker; don't debug dependencies it introduced.
      - Proportionality never bypasses safety, profile, credential,
        issue-tracking, authorization, or deployment gates.

      ## Worktrees

      - Make repository changes in a linked worktree on a task branch.
        Read-only work needs none. John may opt out with "no worktree" or
        "work in place"; never infer an exemption.
      - Before writing, check `git worktree list --porcelain` and
        `git rev-parse --path-format=absolute --git-dir --git-common-dir`
        (resolve symlinks; a feature branch in the primary checkout is not a
        worktree). Reuse this task's worktree, otherwise create one from local
        `main` with a kebab-case slug (fixes and chores included):

        ```bash
        git -C "$repo_root" worktree add -b "feature/$slug" "$repo_root/.worktrees/$slug" main
        ```

        If `main` is missing or the branch/path exists but is unsuitable, stop
        and report; never adopt another task's worktree or change the base.
      - Claude: enter it with a standalone `cd "$task_path"` and verify with
        `pwd -P`; staying there is expected. Note the session start directory
        for cleanup. Pi: shell `cd` doesn't move the agent, so use absolute paths,
        `git -C`, and `mise -C "$task_path" exec --`.
      - Preserve unrelated changes, credentials, sessions, and other worktrees.
        A worktree is not permission to switch profiles or copy credentials.

      ## Authorization

      - Never commit, merge, push, or remove a worktree without authorization.
      - An actual personal `/wrap` invocation authorizes the scoped commit,
        guarded rebase/fast-forward integration, and worktree cleanup its
        command describes. Mentioning or quoting `/wrap`, reading its prompt
        file, or "wrap up" does not. `/wrap` also authorizes a plain push of
        integrated local `main` unless invoked as `/wrap no-push`. It
        authorizes a rebuild or deployment only where the repository's
        `AGENTS.md` says `/wrap` deploys.
      - John asking to archive a session (this one, or a task you spawned or
        are told to relay to) is the authorization, with or without `/wrap`:
        archive with `switchyard stop_task` without asking again or leaving the
        archive to John. Never emit a text-only reply saying you are archiving —
        text without a tool call ends the turn and leaves the session unarchived.
        Pass the handoff in `stop_task`'s `handoff` parameter (when supported)
        or emit the handoff text and the `stop_task` call in the same assistant
        turn. **Never archive when `/wrap` hits a blocker (`WRAP BLOCKED`):**
        leave the session open so John can resolve it. Outside a blocked `/wrap`
        (including a standalone archive request or John saying to archive anyway
        after seeing a blocker), open cards and pending pushes or deploys go in
        the handoff; only `stop_task` refusing uncommitted changes stops it.
      - An authorized deployment includes clean fast-forward sync of a deployment
        host's `main` to integrated local `main`, without separate merge
        permission; stop on dirty source, divergence, or uncertain ownership.

      ## Commits

      - Before staging or committing, read the personal `authoring-commits` skill
        (`~/.config/claude-personal/skills/` for Claude, `~/.config/pi/skills/`
        for Pi, `~/.gemini/config/skills/` for agy; prefer it over packaged copies) and the
        `implementation-attribution` skill. Not for work profiles.
      - During implementation, keep an attribution handoff in the conversation
        (branch/worktree, each contributor's model, paths it authored, evidence)
        and include it in completion summaries.

      ## Delegation

      - When John explicitly asks for a sub-agent, delegating is your first
        substantive action: no investigation, task-file reads, card actions,
        edits, or tests beforehand. Read the `delegating-to-subagents` skill for
        the brief, handoff, and failure recovery (reading it counts as launch
        discovery).

    ''
    + htmlReportInstructions
    + omarchyInstructions
    + config.agentProjects.hostInstructions;
  workInstructions =
    builtins.readFile ./agent-projects/work-instructions.md
    + "\n"
    + attributionInstructions
    + taskScopeInstructions
    + deploymentInstructions
    + delegationInstructions
    + "\n"
    + htmlReportInstructions
    + omarchyInstructions
    + config.agentProjects.hostInstructions;
in {
  imports = [./agent-skills.nix ./claude-work-context.nix ./deployment-coordination.nix];

  options.agentProjects.hostInstructions = lib.mkOption {
    type = lib.types.lines;
    default = "";
    description = "Host-specific rules appended to personal and work agents' global instructions.";
  };

  # Shared directory context, not project dependencies (those stay in mise).
  # Home Manager must fail on unexpected unmanaged files; review/back up before
  # adopting an existing config rather than forcing replacement.
  config.home.file = {
    "dev/src/amfaro/mise.toml".source = ./agent-projects/amfaro-mise.toml;
    # Global instructions follow the selected profile even outside the parent tree.
    ".config/pi/AGENTS.md".text = personalInstructions;
    ".config/claude-personal/CLAUDE.md".text = personalInstructions;
    ".config/pi-work/AGENTS.md".text = workInstructions;
    ".config/claude-gmatter/CLAUDE.md".text = workInstructions;
  };

  # Trust only this managed config, after the new generation's link is installed.
  # Use a pinned CLI for activation, without replacing either host's native mise.
  config.home.activation.trustAgentProjects = lib.hm.dag.entryAfter ["linkGeneration"] ''
    $DRY_RUN_CMD ${lib.getExe pkgs.mise} trust ${lib.escapeShellArg amfaroConfig}
  '';

  # Write .fizzy.yaml only into existing checkouts: creating a missing project
  # directory would make switchyard skip its clone. Each repo's info/exclude
  # keeps the file out of Git; a still-tracked copy is left alone with a warning.
  config.home.activation.fizzyProjectConfig = lib.hm.dag.entryAfter ["linkGeneration"] (
    ''
      fizzyProject() {
        local dir=$1 src=$2 git=${lib.getExe pkgs.git} exclude
        [[ -e "$dir/.git" ]] || return 0
        if $git -C "$dir" ls-files --error-unmatch .fizzy.yaml >/dev/null 2>&1; then
          warnEcho "$dir/.fizzy.yaml is tracked by Git; untrack it to manage it"
          return 0
        fi
        if ! $git -C "$dir" check-ignore -q .fizzy.yaml; then
          exclude=$($git -C "$dir" rev-parse --path-format=absolute --git-path info/exclude)
          $DRY_RUN_CMD mkdir -p "$(dirname "$exclude")"
          $DRY_RUN_CMD sh -c 'printf "%s\n" .fizzy.yaml >> "$1"' sh "$exclude"
        fi
        cmp -s "$src" "$dir/.fizzy.yaml" || $DRY_RUN_CMD install -m 600 "$src" "$dir/.fizzy.yaml"
      }
    ''
    + lib.concatMapStrings (p: ''
      fizzyProject ${lib.escapeShellArg p.dir} ${p.file}
    '')
    fizzyProjects
  );
}
