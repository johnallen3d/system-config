#!/usr/bin/env bash

# Refresh remote-tracking refs and remove safe, inactive worktrees whose
# configured upstream branch has disappeared.

set -u

plugin_root=${HERDR_PLUGIN_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}
# shellcheck source=./config.sh
source "$plugin_root/config.sh"
# shellcheck source=./helpers.sh
source "$plugin_root/helpers.sh"
# shellcheck source=./lifecycle.sh
source "$plugin_root/lifecycle.sh"

if [[ $(worktrunk_cleanup_deleted_upstreams) != true ]]; then
  exit 0
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  exit 0
fi

if ! git fetch --all --prune --quiet; then
  printf '\033[33mWarning:\033[0m unable to refresh remotes; skipped deleted-upstream cleanup\n' >&2
  exit 0
fi

current_branch=$(git branch --show-current 2>/dev/null || true)
wtitems=$(worktrunk_worktree_items) || exit 0

while IFS= read -r branch; do
  tracking=$(LC_ALL=C git for-each-ref --format='%(upstream:track)' "refs/heads/$branch")
  if [[ $tracking != "[gone]" ]]; then
    continue
  fi

  if [[ $branch == "$current_branch" ]]; then
    printf '\033[33mWarning:\033[0m upstream for current worktree %s was deleted; switch away before cleanup\n' "$branch" >&2
    continue
  fi

  wtpath=$(printf '%s\n' "$wtitems" | worktrunk_worktree_path "$branch")
  wsid=$(worktrunk_open_workspace_id "$wtpath")

  if wt remove --foreground "$branch"; then
    worktrunk_close_worktree_ui "$wsid" "$wtpath"
  else
    printf '\033[33mWarning:\033[0m retained deleted-upstream worktree %s\n' "$branch" >&2
  fi
done < <(printf '%s\n' "$wtitems" | worktrunk_worktree_branches)
