{
  config,
  lib,
  pkgs,
  ...
}: let
  amfaroConfig = "${config.home.homeDirectory}/dev/src/amfaro/mise.toml";
  attributionInstructions = builtins.readFile ./agent-projects/attribution-instructions.md;
  delegationInstructions = builtins.readFile ./agent-projects/delegation-instructions.md;
  taskScopeInstructions = builtins.readFile ./agent-projects/task-scope-instructions.md;
  deploymentInstructions = builtins.readFile ./agent-projects/deployment-instructions.md;
  omarchyInstructions = lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''

    ## Arch/Omarchy

    This is standalone Home Manager on Arch/Omarchy, not macOS or NixOS.
    Never run macOS rebuild tasks here or change Omarchy shell/desktop settings.
    See docs/omarchy-agents.md in system-config for application and authentication.
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
        file, or "wrap up" does not. `/wrap` never authorizes a rebuild or push.
      - An authorized deployment includes clean fast-forward sync of a deployment
        host's `main` to integrated local `main`, without separate merge
        permission; stop on dirty source, divergence, or uncertain ownership.

      ## Commits

      - Before staging or committing, read the personal `authoring-commits` skill
        (`~/.config/claude-personal/skills/` for Claude, `~/.config/pi/skills/`
        for Pi; prefer it over packaged copies) and the
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
    + omarchyInstructions;
  workInstructions =
    builtins.readFile ./agent-projects/work-instructions.md
    + "\n"
    + attributionInstructions
    + taskScopeInstructions
    + deploymentInstructions
    + delegationInstructions
    + omarchyInstructions;
in {
  imports = [./agent-skills.nix ./claude-work-context.nix ./deployment-coordination.nix];

  # Shared directory context, not project dependencies (those stay in mise).
  # Home Manager must fail on unexpected unmanaged files; review/back up before
  # adopting an existing config rather than forcing replacement.
  home.file = {
    "dev/src/amfaro/mise.toml".source = ./agent-projects/amfaro-mise.toml;
    # Global instructions follow the selected profile even outside the parent tree.
    ".config/pi/AGENTS.md".text = personalInstructions;
    ".config/claude-personal/CLAUDE.md".text = personalInstructions;
    ".config/pi-work/AGENTS.md".text = workInstructions;
    ".config/claude-gmatter/CLAUDE.md".text = workInstructions;
  };

  # Trust only this managed config, after the new generation's link is installed.
  # Use a pinned CLI for activation, without replacing either host's native mise.
  home.activation.trustAgentProjects = lib.hm.dag.entryAfter ["linkGeneration"] ''
    $DRY_RUN_CMD ${lib.getExe pkgs.mise} trust ${lib.escapeShellArg amfaroConfig}
  '';
}
