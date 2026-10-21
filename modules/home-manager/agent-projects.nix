{
  config,
  lib,
  pkgs,
  ...
}: let
  amfaroConfig = "${config.home.homeDirectory}/dev/src/amfaro/mise.toml";
  delegationInstructions = builtins.readFile ./agent-projects/delegation-instructions.md;
  taskScopeInstructions = builtins.readFile ./agent-projects/task-scope-instructions.md;
  deploymentInstructions = builtins.readFile ./agent-projects/deployment-instructions.md;
  omarchyInstructions = lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''

    ## Arch/Omarchy

    This is standalone Home Manager on Arch/Omarchy, not macOS or NixOS.
    Never run macOS rebuild tasks here or change Omarchy shell/desktop settings.
    See docs/omarchy-agents.md in system-config for application and authentication.
  '';
  personalInstructions =
    ''
      # Personal agent instructions

      - Always respond in English. The user's name is John Allen.
      - Respect `PI_CODING_AGENT_DIR` and `CLAUDE_CONFIG_DIR`; keep profiles,
        credentials, and sessions separate.

      ## Personal worktrees by default

      - Perform repository changes in a dedicated linked Git worktree on a
        task-specific branch. Read-only investigation needs no worktree.
        John can explicitly opt out for the current task with "no worktree" or
        "work in place"; never infer an exemption because a task looks simple.
      - Before repository writes, use `git worktree list --porcelain` and
        `git rev-parse --path-format=absolute --git-dir --git-common-dir` to
        identify the primary checkout and linked worktrees. Resolve symlinks;
        a feature branch in the primary checkout is not a linked worktree.
      - Reuse a suitable linked worktree belonging to this task. Otherwise create
        it from local `main`, with a simple kebab-case task slug, at the primary
        repository's `.worktrees/<slug>` on `feature/<slug>` (including fixes
        and chores):

        ```bash
        git -C "$repo_root" worktree add -b "feature/$slug" "$repo_root/.worktrees/$slug" main
        ```

        `repo_root` is the absolute primary checkout path. If `main` is missing
        or the branch/path already exists but is unsuitable, stop and report
        the blocker; never adopt another task's worktree or substitute a base.
      - Work in the task worktree during implementation. In Claude Code, enter it
        with a standalone `cd "$task_path"` and verify with `pwd -P`. Top-level
        Bash `cd` can persist across tool calls; this is expected task cwd, not
        drift. Do not restore the primary directory between task commands.
        Record the verified session start directory before task commands so
        cleanup can distinguish task cwd from the actual session anchor.
      - In Pi, shell `cd` does not move the agent's cwd. Use absolute worktree
        paths for file tools and `git -C "$task_path"`,
        `mise -C "$task_path" exec -- ...`, or `(cd "$task_path" && ...)`
        for task commands. Do not simulate a session move with `process.chdir`.
        Keep edits, builds, tests, and task Git operations in the task worktree.
      - Before `/wrap` removes the task worktree, return to the primary checkout.
        In Claude, run a standalone `cd "$repo_root"` in Bash, then verify the
        updated harness cwd and a fresh plain `pwd -P` in a separate call.
        A normal task-directory change needs no relaunch or correction during work.
        If the actual session was launched inside the task worktree, a Bash `cd`
        alone does not relocate its session anchor: require a verified
        resume/relaunch at the primary repository root before removal.
        Retain the worktree if the actual session anchor or current cwd is uncertain.
        A subshell, command cwd override, `wt switch`, or Pi `process.chdir` is not
        proof of a safe session cwd. Never delete the running session's directory.
      - Preserve unrelated changes, credentials, sessions, and other worktrees.
        Keep both profile variables and project mise context; use `mise exec`
        explicitly for noninteractive project commands. A worktree is not
        permission to switch profiles or copy credentials.
      - Never commit, merge, push, or remove a worktree without authorization.
        An actual personal `/wrap` invocation authorizes scoped commit,
        guarded rebase of this task's own unpublished local commits onto existing
        local `main` when needed, fast-forward integration, and safe task-worktree
        cleanup under the personal command's lifecycle. Uncertain publication or
        task ownership, conflicts, and signing/hook failures stop that sequence. Ordinary "wrap up",
        quoting or mentioning `/wrap`, and reading a prompt file through tools
        do not authorize that lifecycle. `/wrap` never authorizes a rebuild
        or push by itself; repository deployment and card-closure gates remain.

    ''
    + taskScopeInstructions
    + deploymentInstructions
    + delegationInstructions
    + omarchyInstructions;
  workInstructions =
    builtins.readFile ./agent-projects/work-instructions.md
    + "\n"
    + taskScopeInstructions
    + deploymentInstructions
    + delegationInstructions
    + omarchyInstructions;
in {
  imports = [./claude-work-context.nix ./deployment-coordination.nix];

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
