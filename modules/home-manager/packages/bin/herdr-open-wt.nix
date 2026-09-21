{pkgs, ...}:
pkgs.writeShellScriptBin "herdr-open-wt" ''
  set -euo pipefail

  list="$(${pkgs.herdr}/bin/herdr worktree list --json)"
  root="$(printf '%s' "$list" | ${pkgs.jq}/bin/jq -er '.result.source.repo_root')"

  printf '%s' "$list" \
    | ${pkgs.jq}/bin/jq -r '.result.worktrees[] | select(.is_linked_worktree) | .path' \
    | while IFS= read -r path; do
      ${pkgs.herdr}/bin/herdr worktree open \
        --cwd "$root" \
        --path "$path" \
        --no-focus
    done
''
