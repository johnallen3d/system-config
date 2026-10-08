"""Exercise the patched picker with private Git repositories and mocked UI.

Usage: python3 tests/herdr-worktrunk-short-names.py /path/to/patched/plugin
Requires Bash, Git, jq, and Worktrunk on PATH. No real Herdr server is contacted.
Also runs inside the plugin's Nix derivation.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

plugin = Path(sys.argv[1]).resolve()
real_wt = shutil.which("wt")
assert real_wt, "Worktrunk required"
TEMPLATE = 'worktree-path = "{{ repo_path }}/.worktrees/{{ branch[8:] | sanitize }}"'


def run(args, env, cwd, check=True, input=""):
    result = subprocess.run(args, env=env, cwd=cwd, input=input, text=True,
                            capture_output=True, timeout=30)
    if check:
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


with tempfile.TemporaryDirectory(prefix="herdr-short-names-") as temporary:
    root = Path(temporary).resolve()
    bins = root / "bin"
    bins.mkdir()

    def stub(name, body):
        path = bins / name
        path.write_text(f"#!{sys.executable}\n" + body)
        path.chmod(0o755)

    stub("fzf", '''import os, sys
from pathlib import Path
p = Path(os.environ["CASE"])
(p / "candidates").write_text(sys.stdin.read())
(p / "fzf-args").write_text("\\n".join(sys.argv[1:]))
sys.stdout.write(os.environ["CHOICE"])
sys.exit(int(os.environ.get("FZF_EXIT", "0")))
''')
    stub("wt", '''import json, os, subprocess, sys
from pathlib import Path
p = Path(os.environ["CASE"])
a = sys.argv[1:]
with (p / "wt-calls").open("a") as f:
    f.write(json.dumps(a) + "\\n")
if a[0] == "list" and "MOCK_LIST" in os.environ:
    print(os.environ["MOCK_LIST"])
    sys.exit(0)
if a[0] == "switch":
    if os.environ.get("WT_FAIL"):
        print("simulated hook failure", file=sys.stderr)
        sys.exit(1)
    if "MOCK_RESULT" in os.environ:
        print(os.environ["MOCK_RESULT"])
        sys.exit(0)
sys.exit(subprocess.call([os.environ["REAL_WT"], *a]))
''')
    stub("herdr", '''import json, os, subprocess, sys
from pathlib import Path
p = Path(os.environ["CASE"])
a = sys.argv[1:]
with (p / "herdr-calls").open("a") as f:
    f.write(json.dumps(a) + "\\n")
if a[:2] == ["worktree", "list"]:
    if os.environ.get("ROOT_FAIL"):
        print('{"result":{}}')
    else:
        print(json.dumps({"result":{"source":{
            "repo_root": os.environ["REPO"], "repo_name":"repo",
            "source_workspace_id": None if os.environ.get("NO_ROOT_SPACE") else "w1"}}}))
elif a[:2] == ["tab", "create"]:
    env = dict(x.split("=", 1) for i, x in enumerate(a) if i and a[i-1] == "--env")
    (p / "tab-env").write_text(json.dumps(env))
    print(json.dumps({"result":{"root_pane":{"pane_id":"w1:p2","tab_id":"w1:t2"}}}))
elif a[:2] == ["pane", "run"]:
    env = os.environ.copy()
    env.update(json.loads((p / "tab-env").read_text()))
    env["WORKTRUNK_BIN"] = str(Path(__file__).with_name("wt"))
    # Use Worktrunk's real Bash integration, just as a new interactive tab does.
    if env.get("TAB_SHELL") == "fish":
        command = 'source ("$REAL_WT" config shell init fish | psub); ' + a[3]
        shell = ["fish", "--no-config"]
    else:
        command = 'eval "$("$REAL_WT" config shell init bash)"; ' + a[3]
        shell = ["bash", "--noprofile", "--norc"]
    sys.exit(subprocess.call([*shell, "-c", command], env=env))
''')
    # Avoid popup error delays without suppressing failures.
    stub("sleep", "pass\n")

    index = 0

    def case(mode="workspace", config=""):
        global index
        index += 1
        directory = root / str(index)
        repo = directory / "repo"
        directory.mkdir()
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("WORKTRUNK_", "WT_", "HERDR_", "MOCK_"))}
        env.update(PATH=f"{bins}:{os.environ['PATH']}", CASE=str(directory),
                   REPO=str(repo), REAL_WT=real_wt, HOME=str(directory / "home"),
                   XDG_CONFIG_HOME=str(directory / "config"),
                   XDG_CONFIG_DIRS=str(directory / "system"),
                   WORKTRUNK_CONFIG_PATH=str(directory / "wt.toml"),
                   WORKTRUNK_SYSTEM_CONFIG_PATH=str(directory / "empty.toml"),
                   HERDR_PLUGIN_ROOT=str(plugin), HERDR_BIN_PATH=str(bins / "herdr"),
                   HERDR_PLUGIN_CONFIG_DIR=str(directory / "plugin-config"),
                   HERDR_WORKSPACE_ID="w1", NO_COLOR="1", GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL=str(directory / "gitconfig"))
        (directory / "plugin-config").mkdir()
        (directory / "plugin-config/config.toml").write_text(f'open_mode = "{mode}"\n')
        (directory / "wt.toml").write_text(
            'worktree-path = "{{ repo_path }}/.worktrees/{{ branch | sanitize }}"\n'
            '[list]\njson-schema = 2\n' + config)
        run(["git", "init", "-q", "-b", "main", str(repo)], env, directory)
        run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com",
             "commit", "-q", "--allow-empty", "-m", "init"], env, repo)
        return directory, repo, env

    def git(c, *args):
        return run(["git", *args], c[2], c[1]).stdout.strip()

    def calls(c, name):
        path = c[0] / f"{name}-calls"
        return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []

    def switch_calls(c):
        return [x for x in calls(c, "wt") if x[0] == "switch"]

    def opened(c):
        return [x for x in calls(c, "herdr") if x[:2] in
                (["worktree", "open"], ["tab", "rename"])]

    def pick(c, choice, *args, failure=False, **extra):
        env = c[2] | {"CHOICE": choice} | extra
        result = run(["bash", str(plugin / "picker.sh"), *args], env, c[1], check=False)
        assert (result.returncode != 0) == failure, (choice, result.returncode,
                                                    result.stdout, result.stderr)
        if failure:
            assert not opened(c), calls(c, "herdr")
        return result

    def label(c, expected):
        actions = opened(c)
        assert actions, calls(c, "herdr")
        a = actions[-1]
        actual = a[-1] if a[:2] == ["tab", "rename"] else a[a.index("--label") + 1]
        assert actual == expected, (actual, expected)

    for mode in ("workspace", "tab"):
        for name, slug in (("api-work", "api-work"), ("feature/api-work", "api-work"),
                           ("feature/team/api", "team-api"), ("fix/api-work", "fix-api-work"),
                           ("feature/quote'$(echo_owned)", "quote'$(echo_owned)")):
            c = case(mode)
            pick(c, name, FZF_EXIT="1")
            target = name if "/" in name else f"feature/{name}"
            argv = switch_calls(c)[0]
            assert argv[:3] == ["switch", "--create", target], argv
            feature = target.startswith("feature/")
            assert ("--config-set" in argv) == feature, argv
            if feature:
                assert argv[argv.index("--config-set") + 1] == TEMPLATE
            assert (c[1] / ".worktrees" / slug).is_dir(), (name, calls(c, "wt"))
            label(c, slug if feature else target)
            assert "--yes" not in argv and "--no-hooks" not in argv and "--clobber" not in argv

        c = case(mode)
        git(c, "branch", "api-work")
        git(c, "branch", "feature/api-work")
        pick(c, "api-work")
        assert switch_calls(c)[0][:2] == ["switch", "api-work"]
        assert "--config-set" not in switch_calls(c)[0]
        label(c, "api-work")

        c = case(mode)
        git(c, "branch", "feature/api-work")
        pick(c, "api-work", "--create-base=current")
        assert switch_calls(c)[0][:2] == ["switch", "feature/api-work"]
        assert "--base" not in switch_calls(c)[0]
        label(c, "api-work")

        c = case(mode)
        old = c[1] / ".worktrees/feature-api-work"
        git(c, "worktree", "add", "-q", "-b", "feature/api-work", str(old))
        pick(c, "api-work")
        assert old.is_dir() and not (c[1] / ".worktrees/api-work").exists()
        label(c, "feature-api-work")

        c = case(mode)
        git(c, "checkout", "-q", "-b", "source")
        git(c, "-c", "user.name=test", "-c", "user.email=test@example.com",
            "commit", "-q", "--allow-empty", "-m", "source")
        pick(c, "from-current", "--create-base=current")
        a = switch_calls(c)[0]
        assert a[a.index("--base") + 1] == "@", a
        assert git(c, "rev-parse", "feature/from-current") == git(c, "rev-parse", "source")
        label(c, "from-current")

        c = case(mode)
        git(c, "checkout", "-q", "-b", "source")
        git(c, "-c", "user.name=test", "-c", "user.email=test@example.com",
            "commit", "-q", "--allow-empty", "-m", "source")
        pick(c, "from-default")
        assert "--base" not in switch_calls(c)[0]
        assert git(c, "rev-parse", "feature/from-default") == git(c, "rev-parse", "main")

        c = case(mode)
        run([real_wt, "switch", "--create", "previous", "--no-cd"], c[2], c[1])
        run([real_wt, "switch", "main", "--no-cd"], c[2], c[1] / ".worktrees/previous")
        pick(c, "-")
        assert switch_calls(c)[0][:2] == ["switch", "-"]
        label(c, "previous (-)")

        c = case(mode)
        git(c, "update-ref", "refs/remotes/origin/remote-work", "HEAD")
        pick(c, "origin/remote-work", "--show-with-remotes")
        assert switch_calls(c)[0][:2] == ["switch", "origin/remote-work"]
        assert "--config-set" not in switch_calls(c)[0]

        for shortcut in ("^", "@"):
            c = case(mode)
            pick(c, shortcut)
            assert switch_calls(c)[0][:2] == ["switch", shortcut]
            if mode == "workspace":
                assert "--label" not in opened(c)[0], opened(c)

        for value, exit_code in (("", "0"), ("", "130")):
            c = case(mode)
            pick(c, value, FZF_EXIT=exit_code)
            assert not switch_calls(c) and not calls(c, "herdr")

        for invalid in ("bad name", "feature/", "feature/../bad", "bad..name"):
            c = case(mode)
            pick(c, invalid, failure=True)
            assert not switch_calls(c)

        c = case(mode)
        git(c, "branch", "feature/api-work")
        pick(c, "api\nfeature/api-work")
        assert switch_calls(c)[0][:2] == ["switch", "feature/api-work"]
        c = case(mode)
        git(c, "branch", "feature/api-work")
        pick(c, "api")  # Alt+Enter returns just the query, not the highlighted match.
        assert switch_calls(c)[0][:3] == ["switch", "--create", "feature/api"]
        assert "--bind=alt-enter:print-query" in (c[0] / "fzf-args").read_text()
        assert "feature/<name>" in (c[0] / "fzf-args").read_text()

        c = case(mode)
        collision = c[1] / ".worktrees/api-work"
        collision.mkdir(parents=True)
        (collision / "keep").write_text("unrelated")
        pick(c, "api-work", failure=True)
        assert (collision / "keep").read_text() == "unrelated"
        assert str(collision) not in git(c, "worktree", "list", "--porcelain")

        c = case(mode)
        git(c, "worktree", "add", "-q", "-b", "feature/team-api",
            str(c[1] / ".worktrees/team-api"))
        pick(c, "feature/team/api", failure=True)
        assert git(c, "-C", str(c[1] / ".worktrees/team-api"), "branch", "--show-current") == "feature/team-api"

        # User-level hooks are trusted and synchronous; no approval bypass needed.
        c = case(mode, '\n[pre-start]\nproof = "echo hook-ran > hook-proof"\n')
        pick(c, "hook-test")
        assert (c[1] / ".worktrees/hook-test/hook-proof").read_text().strip() == "hook-ran"
        c = case(mode, '\n[pre-start]\nfail = "exit 1"\n')
        pick(c, "hook-fail", failure=True)

        print(f"PASS {mode}: naming, refs, base, escaping, cancellation, collisions, hooks")

    # Fish is optional locally, but explicitly available in the Nix build.
    if shutil.which("fish"):
        for name in ("feature/fish'$(echo_owned)", "feature/team/fish"):
            c = case("tab")
            pick(c, name, TAB_SHELL="fish")
            assert switch_calls(c)[0][:3] == ["switch", "--create", name]
            label(c, name[8:].replace("/", "-"))
        c = case("tab")
        pick(c, "fish-hook-fail", WT_FAIL="1", TAB_SHELL="fish", failure=True)
        print("PASS Fish tab argv, short labels, and failed-switch relabel guard")
    else:
        print("SKIP Fish tab checks: fish unavailable")

    # Exercise plain-read fallback with a private PATH containing no fzf.
    no_fzf = root / "no-fzf"
    no_fzf.mkdir()
    # A mise shim needs its original basename/PATH; prefer actual executables.
    binary_path = ":".join(p for p in os.environ["PATH"].split(":") if "/shims" not in p)
    for cmd in ("bash", "git", "jq", "basename", "awk", "sed", "tail", "head", "sleep"):
        (no_fzf / cmd).symlink_to(shutil.which(cmd, path=binary_path))
    for cmd in ("wt", "herdr"):
        (no_fzf / cmd).symlink_to(bins / cmd)
    c = case()
    env = c[2] | {"PATH": str(no_fzf)}
    result = run([shutil.which("bash"), str(plugin / "picker.sh")], env, c[1], input="plain-name\n")
    assert "feature/<name>" in result.stdout
    label(c, "plain-name")
    c = case()
    run([shutil.which("bash"), str(plugin / "picker.sh")], c[2] | {"PATH": str(no_fzf)}, c[1])
    assert not switch_calls(c)  # EOF cancels.
    print("PASS plain-read naming prompt and EOF cancellation")

    # Mock only resolution that would otherwise require a forge/network or old state.
    for shortcut in ("-", "pr:42", "mr:42", "https://github.com/test/repo/pull/42"):
        c = case()
        checkout = c[1] / "resolved"
        checkout.mkdir()
        pick(c, shortcut, MOCK_RESULT=json.dumps(dict(branch="resolved-branch", path=str(checkout))))
        assert switch_calls(c)[0][:2] == ["switch", shortcut]
        label(c, f"resolved-branch ({shortcut})")

    c = case()
    checkout = c[1] / "api-work"
    checkout.mkdir()
    pick(c, "api-work", MOCK_RESULT='{}', MOCK_LIST=json.dumps({"items": [
        {"branch": "feature/api-work", "worktree": {"path": str(checkout), "main": False}}]}))
    label(c, "api-work")
    for mock in (dict(MOCK_RESULT="not-json"), dict(MOCK_RESULT="{}", MOCK_LIST="[]"),
                 dict(ROOT_FAIL="1"), dict(WT_FAIL="1")):
        c = case()
        result = pick(c, "api-work", failure=True, **mock)
        assert result.stdout or result.stderr
    c = case()
    pick(c, "main", NO_ROOT_SPACE="1")
    assert any(a[:2] == ["workspace", "create"] for a in calls(c, "herdr"))
    assert "--label" not in opened(c)[0]
    print("PASS shortcuts, schema-2 fallback, invalid JSON/path/root, and root label guard")

print(f"herdr-worktrunk-short-names: {index} isolated scenarios passed")
