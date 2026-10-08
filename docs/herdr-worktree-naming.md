# Short-name worktrees in Herdr

`Cmd+Shift+N` keeps the Worktrunk popup and branch picker. Entering a new bare
name creates a feature branch while keeping the checkout and workspace label short:

| Input | Branch | Checkout | Herdr label |
| --- | --- | --- | --- |
| `api-work` | `feature/api-work` | `.worktrees/api-work` | `api-work` |
| `feature/api-work` | `feature/api-work` | `.worktrees/api-work` | `api-work` |
| `feature/team/api` | `feature/team/api` | `.worktrees/team-api` | `team-api` |
| `fix/api-work` | `fix/api-work` | `.worktrees/fix-api-work` | `fix/api-work` |

The non-feature example assumes the repository's default Worktrunk path template.
Explicit other namespaces escape the feature policy and keep normal Worktrunk
path/label behavior. The global path template is unchanged.

- Exact existing bare refs win. If `api-work` exists, it is switched to unchanged.
- Otherwise an existing `feature/api-work` is switched to rather than recreated.
- Existing checkouts are never moved. Old feature checkout directory names can
  remain visible as labels; migration is not part of this feature.
- Enter selects the highlighted fuzzy match. Alt+Enter forces the typed query,
  but still performs reference checks before creating anything.
- Remote refs, `^`, `-`, `@`, PR/MR shortcuts, and URLs retain Worktrunk resolution.
- New branches use Worktrunk's default base, or `--base @` for the current-base
  action. Existing branches do not receive a base override.
- Cancellation/empty input creates nothing. Git validates new branch names;
  Worktrunk refuses directory/slug collisions without deleting or adopting them.
- Worktrunk handles creation and hooks in both workspace and tab modes. Failed
  switches do not open a worktree workspace or trigger a tab rename. Tab failures
  remain visible in the newly opened terminal.
- The repository's main workspace keeps its project label.

## Maintenance and validation

The pinned plugin is patched by
`modules/home-manager/patches/herdr-worktrunk-short-names.patch`. Patch application
rejects fuzz. Its Nix derivation runs shell syntax checks, ShellCheck, upstream
shell tests, and the local regression suite with temporary Git repositories,
real Worktrunk hooks/templates, and mocked Herdr/fzf. No real Herdr session is
modified by those tests.

To repeat the local suite against a built plugin:

```sh
python3 tests/herdr-worktrunk-short-names.py /nix/store/<built-plugin>
```

After source changes, apply on macOS using `mise run nix-rebuild --switch-only`,
then run `herdr server reload-config` inside a Herdr-managed pane. The next popup
loads the linked plugin. Interactive smoke tests should use a disposable
repository/workspace with John's approval, not a live project.

Rollback removes the patch/application and rebuilds/reloads via the same workflow.
It does not remove previously created branches or worktrees.
