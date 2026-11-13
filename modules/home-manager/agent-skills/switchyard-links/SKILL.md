---
name: switchyard-links
description: Use when a task branch gains a card, issue, or PR.
---

# Link Switchyard tasks to their work items

Switchyard shows a task's cards, issues, and PRs in the tab picker. It learns
them only from the launch prompt or work item, from `Fixes #N` in commits not
yet merged, and from the branch's links. Link anything else yourself, or the
task won't show it.

## When

On any task branch, as soon as you create, adopt, or are pointed at a work
item for the task, link it. Don't wait for the end, and don't try to work out
whether Switchyard tracks the branch: nothing in the session says, and a link
on an untracked branch is harmless. This covers:

- a card or issue you create or choose partway through the task
- a card a completion flow (`/wrap` or a work equivalent) creates for
  untracked work
- a PR you open for the branch

Links live in the branch's git config, so link before committing,
integrating, or removing the worktree. Once the branch is gone, linking can't
be done. Create or choose the card before the commit too, so the commit
message can also say `Fixes #N`.

## How

Run these from the task worktree:

```bash
switchyard link REF      # add one or more refs
switchyard link          # list the branch's links
switchyard unlink REF    # remove one
```

REF is `fizzy:123` or a Fizzy card URL, `#42` or `42` (an issue, or a card
when the project's tracker is a Fizzy board), `OWNER/REPO#42`, `pr:57`, or a
GitHub issue or PR URL. Prefer an explicit form (`fizzy:N`, `OWNER/REPO#N`, or
a URL) when the project's tracker is unclear. Linking an existing ref is a
no-op. Afterwards, check that the ref shows up in `switchyard link`.

Linking is bookkeeping. It doesn't need extra authorization and grants none.
It's not a commit, so it doesn't affect a clean-status check.
