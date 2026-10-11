#!/usr/bin/env python3
"""Validate #755/#758 native staging; no inference, polling or production vault.

Default: source/lock regression checks. --installed: actual Omarchy generation,
including CLI/doctor/fixed checks in transient services with the installed environment.
Optional --vault-sources/--private-skills run only the isolated disposable operator suite.
Doctor expects absent model credentials plus baseline's exact Nix-layout advisory.
"""

import argparse
import json
import os
import re
import shlex
import stat
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = "a19160bbf02dc37c57ff47cf0eaa4a3ab8ee43dc"
VERSION = "0.21.2"
NATIVE_VERSIONS = {"python": "3.13.14", "uv": "0.11.32", "node": "26.5.0", "npm": "12.0.2"}


def source_checks():
    flake = (ROOT / "flake.nix").read_text()
    host = (ROOT / "hosts/omarchy.nix").read_text()
    module = (ROOT / "modules/home-manager/omarchy-hermes.nix").read_text()
    lock = json.loads((ROOT / "flake.lock").read_text())
    node = lock["nodes"][lock["nodes"]["root"]["inputs"]["hermes"]]
    assert node["locked"]["rev"] == REVISION
    assert REVISION in flake
    assert 'nativeHermes.enable = true;' in host
    assert '../modules/home-manager/omarchy-hermes.nix' in host
    assert 'lib.mkIf cfg.enable' in module and 'lib.mkEnableOption' in module
    assert 'RefuseManualStart = true;' in module and 'WantedBy' not in re.sub(r'#[^\n]*', '', module)
    assert 'env -i' in module and 'HERMES_MANAGED = "home-manager"' in module
    assert 'platforms.telegram.enabled = false;' in module
    assert 'platform_toolsets' in module and 'cli = [];' in module
    assert 'home.file.".local/bin/hermes"' not in module
    assert 'home.sessionVariables' not in module
    assert 'EnvironmentFile' not in module
    assert 'python312 = runtimePkgs.python313;' in module
    assert 'callPackage = runtimePkgs.lib.callPackageWith runtimeScope;' in module
    for p in (ROOT / "hosts").glob("*.nix"):
        if p.name != "omarchy.nix" and not p.name.startswith("."):
            assert 'omarchy-hermes.nix' not in p.read_text(), p
    print("PASS source: pinned input, Omarchy-only opt-in, isolated seed, blocked startup")
    assert 'vault-check' in module and 'vault-safety-check' in module
    assert '--ro-bind ${lib.escapeShellArg "${homeDir}/notes"} /vault-readonly' in module
    assert 'productionWrites = "DISABLED";' in module
    # Exercise snapshot/restore with synthetic data only, including an external
    # link as inert metadata. Names and note content never enter diagnostics.
    import importlib.util
    spec = importlib.util.spec_from_file_location('vault_safety', ROOT / 'modules/home-manager/hermes-native/vault-safety.py')
    safety = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(safety)
    if not hasattr(os, 'listxattr'):
        # This Mac's Python omits xattr bindings. Synthetic fixture has none;
        # full xattr integrity MUST pass on actual installed Linux, not here.
        safety.os.listxattr = lambda *a, **kw: []
        print('SKIP local xattr coverage: interpreter lacks bindings; installed Linux is mandatory')
    with tempfile.TemporaryDirectory(prefix='hermes-vault-source-') as directory:
        base = Path(directory)
        source = base / 'source'; source.mkdir(mode=0o700)
        (source / 'note.md').write_bytes(b'SYNTHETIC ONLY\\n')
        (source / 'external').symlink_to('/nonexistent-private-host-path')
        result = safety.snapshot(source, base / 'snapshot')
        assert result['integrity'] == result['disposableRestore'] == 'PASS'
        assert safety.manifest(source) == safety.manifest(base / 'snapshot/restore-disposable')
        (source / 'test.sync-conflict-synthetic.md').write_text('SYNTHETIC CONFLICT')
        assert safety.tree_flags(source)['conflicts'] == 1
        original = safety.manifest
        calls = [0]
        def moving(path):
            data = original(path)
            calls[0] += 1
            if calls[0] == 3:
                data['.']['mtime_ns'] += 1
            return data
        safety.manifest = moving
        try:
            safety.snapshot(source, base / 'drift')
        except RuntimeError:
            pass
        else:
            raise AssertionError('moving source snapshot accepted')
        safety.manifest = original
    print('PASS synthetic snapshot/integrity/restore/link preservation and moving-source refusal; production untouched')


def command(argv, *, env=None, timeout=180):
    return subprocess.run(argv, env=env, capture_output=True, text=True, timeout=timeout,
                          check=False, umask=0o077)


def user_service(metadata, arguments, *, operator=None):
    # Match the installed persistent unit, not the caller's login/work profile.
    argv = ["systemd-run", "--user", "--wait", "--pipe", "--collect", "--quiet",
            "--service-type=exec", "--property=UMask=0077",
            "--property=NoNewPrivileges=yes",
            "--property=WorkingDirectory=" + metadata["workspace"]]
    for key, value in sorted(metadata["environment"].items()):
        argv.append("--property=Environment=" + shlex.quote(key + "=" + value))
    # Operator is authored test code, never a public launcher route. Its own
    # bwrap boundary accepts only reviewed code and private skill data read-only.
    executable = operator if operator is not None else [metadata["launcher"], *arguments]
    return command(argv + executable, timeout=700 if operator is not None else 240)


def installed_checks(options):
    home = Path.home()
    generation = (home / ".local/state/nix/profiles/home-manager").resolve(strict=True)
    meta_path = home / ".config/hermes-native/runtime.json"
    metadata = json.loads(meta_path.read_text())
    expected_meta = generation / "home-files/.config/hermes-native/runtime.json"
    assert meta_path.resolve() == expected_meta.resolve()
    assert metadata["version"] == VERSION and metadata["revision"] == REVISION
    assert metadata["stage"] in {"foundation", "capabilities-offline"} and not metadata["gatewayEnabled"]
    capabilities = metadata["stage"] == "capabilities-offline"
    assert not metadata["productionStateTransferred"]
    assert (home / ".local/bin/hermes-native").resolve() == Path(metadata["launcher"])
    assert metadata["environment"]["HERMES_HOME"] == metadata["paths"]["state"]
    assert metadata["environment"]["HOME"] == metadata["paths"]["home"]
    assert metadata["environment"]["TERMINAL_ENV"] == "local"
    assert metadata["environment"]["TERMINAL_CWD"] == metadata["workspace"]
    assert not any(k.startswith(("PI_", "CLAUDE_")) or k.endswith(("TOKEN", "API_KEY"))
                   for k in metadata["environment"])
    for path in metadata["paths"].values():
        p = Path(path)
        assert not p.is_symlink() and p.is_dir()
        assert stat.S_IMODE(p.stat().st_mode) == 0o700
        assert str(p).startswith(str(home) + "/") and "/hermes-native/staging/baseline-0.21.2" in str(p)
    state = Path(metadata["paths"]["state"])
    for name in ["config.yaml", ".env"]:
        p = state / name
        assert not p.is_symlink() and stat.S_IMODE(p.stat().st_mode) == 0o600
    assert (state / ".env").read_bytes() == b"", "Foundation must have no staged credentials"
    staged = (state / 'state-staging.json').exists()
    assert (state / 'auth.json').exists() == staged
    if staged:
        result = user_service(metadata, ['state-check'])
        assert result.returncode == 0 and json.loads(result.stdout)['stateCheck'] == 'PASS'
        print('PASS receipt-verified private #760 import; no queue replay or production authority')
    assert metadata['environment']['NOTEBOOKLM_HOME'] == metadata['paths']['home'] + '/.notebooklm'
    seed = json.loads((state / "config.yaml").read_text())
    assert seed["_config_version"] == 44, "Fresh NAS-baseline seed; no format-50 downgrade/import"
    assert seed["terminal"]["cwd"] == metadata["workspace"]
    assert seed["terminal"]["backend"] == "local"
    assert seed["platforms"]["telegram"]["enabled"] is False
    assert seed["platform_toolsets"] == {"cli": [], "telegram": []}
    assert not seed["mcp_servers"]
    assert seed["plugins"]["enabled"] == (["search", "macros"] if capabilities else [])
    assert "/notes" not in json.dumps(seed)
    # Exercise the actual installed generation's initializer scripts in a new,
    # private disposable workspace, without replacing any existing staging data.
    # Retain the probe for inspection; no destructive cleanup is performed.
    activation = (generation / "activate").read_text()
    scripts = re.findall(r"/nix/store/[^\s']+-hermes-native-staging-(?:directories|config)\.py", activation)
    scripts = list(dict.fromkeys(scripts))
    assert len(scripts) == 2
    fresh_state = Path(tempfile.mkdtemp(prefix="foundation-seed-", dir=metadata["workspace"]))
    fresh_env = dict(metadata["environment"], HERMES_HOME=str(fresh_state))
    for script in scripts:
        result = command([metadata["python"], "-I", script], env=fresh_env)
        assert result.returncode == 0, result.stderr[-400:]
    fresh_config = fresh_state / "config.yaml"
    fresh_seed = json.loads(fresh_config.read_text())
    assert fresh_seed["_config_version"] == seed["_config_version"] == 44
    assert fresh_seed["terminal"] == seed["terminal"]
    assert fresh_seed["plugins"]["enabled"] == [] and not fresh_seed["mcp_servers"]
    if not capabilities:
        assert fresh_seed == seed
    assert stat.S_IMODE(fresh_config.stat().st_mode) == 0o600
    for name in ["cron", "sessions", "memories", "logs", "skills"]:
        assert stat.S_IMODE((fresh_state / name).stat().st_mode) == 0o700
    print("PASS actual installed fresh-seed initialization in isolated workspace; existing state untouched")
    jobs = state / "cron/jobs.json"
    if jobs.exists():
        data = json.loads(jobs.read_text())
        if capabilities:
            assert len(data["jobs"]) == 1
            job = data["jobs"][0]
            assert job["name"] == "pi-cielo-morning-brief" and job["enabled"] is False
            assert job["next_run_at"] is None and job["deliver"] is None and job["failure_deliver"] is None
            assert job["no_agent"] is True and not job["prompt"]
        else:
            assert not data or (isinstance(data, dict) and not data.get("jobs")), "No production schedules"

    unit_path = home / ".config/systemd/user/hermes-native.service"
    expected_unit = generation / "home-files/.config/systemd/user/hermes-native.service"
    assert unit_path.resolve() == expected_unit.resolve()
    unit = unit_path.read_text()
    assert 'RefuseManualStart=true' in unit and 'WantedBy=' not in unit
    assert 'WorkingDirectory=' + metadata["workspace"] in unit
    unit_env = {}
    for line in unit.splitlines():
        if line.startswith("Environment="):
            for pair in shlex.split(line.split("=", 1)[1]):
                key, value = pair.split("=", 1)
                unit_env[key] = value
    assert unit_env == metadata["environment"]
    assert 'StandardOutput=journal' in unit and 'StandardError=journal' in unit
    info = command(["systemctl", "--user", "show", "hermes-native.service",
                    "-p", "ActiveState", "-p", "UnitFileState", "-p", "RefuseManualStart", "-p", "CanStart"])
    assert info.returncode == 0
    assert 'ActiveState=inactive' in info.stdout
    # Home Manager links unit files into the load path; systemd therefore reports
    # 'linked' rather than 'static' even though there is no Install/WantedBy.
    assert any('UnitFileState=' + s in info.stdout for s in ["linked", "static"])
    assert 'RefuseManualStart=yes' in info.stdout and 'CanStart=no' in info.stdout
    print("PASS installed generation, explicit service environment, private mutable staging, gateway inactive/unstartable")

    staged_attributes = {p: (Path(p).read_bytes(), Path(p).stat().st_mtime_ns)
                         for p in json.loads((state / 'state-staging.json').read_bytes())['files']} if staged else {}
    before = dict(os.environ)
    hostile_env = dict(os.environ, HERMES_HOME="/should/not/be/used", HOME="/should/not/be/used",
                       TELEGRAM_BOT_TOKEN="synthetic-not-a-token", OPENAI_API_KEY="synthetic-not-a-key",
                       VAULT_DIR="/should/not/be/used", TERMINAL_ENV="docker")
    result = command([metadata["launcher"], "--version"], env=hostile_env)
    assert result.returncode == 0 and VERSION in result.stdout, result.stderr[-400:]
    for args in [["gateway", "run"], ["chat"], ["run", "hello"], ["cron", "tick"],
                 ["doctor", "--fix"], ["doctor", "--live"], ["setup"], ["pm", "repair"]]:
        result = command([metadata["launcher"], *args])
        assert result.returncode == 64, args
    assert os.environ == before
    print("PASS launcher version and fail-closed production/inference/repair gates; caller environment preserved")

    result = user_service(metadata, ["--version"])
    assert result.returncode == 0 and VERSION in result.stdout, result.stderr[-400:]
    result = user_service(metadata, ["--help"])
    assert result.returncode == 0 and "doctor" in result.stdout, result.stderr[-400:]
    print("PASS actual installed CLI --version/--help in transient user-service environment")
    if 'vaultSafety' in metadata:
        assert metadata['vaultSafety']['productionWrites'] == 'DISABLED'
        for operation in ['vault-check', 'vault-safety-check']:
            result = user_service(metadata, [operation])
            private_log = state / ('logs/' + operation + '-759.log')
            private_log.write_text(result.stdout + result.stderr)
            private_log.chmod(0o600)
            assert result.returncode == 0, 'Installed vault check failed; inspect private log ' + str(private_log)
            print('PASS actual installed ' + operation + ' in persistent-unit environment')
        for arguments in [['vault-check', '/home/johna/notes'], ['vault-safety-check', 'write'], ['vault-write'], ['vault-enable'], ['vault-restore']]:
            assert command([metadata['launcher'], *arguments]).returncode == 64
        print('PASS no public arbitrary vault/task, production enable or restore route')
    result = user_service(metadata, ["doctor"])
    log = state / "logs/foundation-doctor.log"
    # Never persist raw doctor output after importing account/provider state.
    # Even private diagnostic logs must not receive credentials or private names.
    issues = re.findall(r"^\s+\d+\. (.+)$", result.stdout, re.MULTILINE)
    # Baseline doctor returns 0 even with findings: gate diagnostics, not its exit.
    venv = Path(metadata["python"]).parent.parent
    site_packages = venv / "lib/python3.13/site-packages"
    # Baseline doctor_platform.py searches PROJECT_ROOT/{venv,.venv}/bin/hermes
    # even when PROJECT_ROOT is sealed wheel site-packages. Do not patch source,
    # run pip, or fake that checkout layout; validate the actual entry point below.
    expected = ["Run 'hermes setup' to configure API keys",
                f"Reinstall entry point: cd {site_packages} && source venv/bin/activate && pip install -e '.[all]'"]
    allowed = [expected, expected[1:]] if staged else [expected]
    summary = {'exit': result.returncode, 'findings': len(issues),
               'apiKeyAdvisory': expected[0] in issues, 'nixLayoutAdvisory': expected[1] in issues,
               'unexpectedFindings': sum(item not in expected for item in issues),
               'oauthFunctionality': 'Checked separately; never inferred from doctor exit'}
    log.write_text(json.dumps(summary, sort_keys=True) + '\n'); log.chmod(0o600)
    assert result.returncode == 0 and issues in allowed, 'Unexpected doctor semantics; see secret-free private summary'
    assert "Traceback" not in result.stdout + result.stderr
    assert "Python" in result.stdout and "Required Packages" in result.stdout
    entry_point = venv / "bin/hermes"
    assert entry_point.is_file() and os.access(entry_point, os.X_OK)
    result = command([str(entry_point), "--version"], env=dict(metadata["environment"], HERMES_HOME=str(fresh_state)))
    assert result.returncode == 0 and VERSION in result.stdout
    assert staged_attributes == {p: (Path(p).read_bytes(), Path(p).stat().st_mtime_ns) for p in staged_attributes}
    print('PASS CLI/doctor use disposable state; imported payload bytes/mtime unchanged')
    print('PASS doctor smoke: exact advisory semantics; exit 0 is NOT integration/production health; actual entry point passes; ' + json.dumps(summary, sort_keys=True))

    closure = command(["nix-store", "--query", "--requisites", metadata["package"]])
    assert closure.returncode == 0, closure.stderr[-400:]
    forbidden = re.compile(r"^[^-]+-(?:docker(?:-[0-9])?|podman-|containerd-|runc-|singularity-|apptainer-)")
    assert not [p for p in closure.stdout.splitlines() if forbidden.match(Path(p).name)]
    for name in ["docker", "podman", "pi", "claude"]:
        assert not any((Path(p) / name).exists() for p in metadata["environment"]["PATH"].split(":")), name
    for name, version in NATIVE_VERSIONS.items():
        result = command([metadata[name], "--version"], env=metadata["environment"])
        assert result.returncode == 0 and version in result.stdout, name
        print("PASS pinned " + name + ": " + result.stdout.strip())
    assert metadata["pythonVersion"] == NATIVE_VERSIONS["python"]
    # Read only immutable source and an in-memory database: no state import,
    # NAS access, model calls, plugin enablement or private content inspection.
    probe = '''
import hashlib, importlib.metadata, json, sqlite3, sys, tomllib
from pathlib import Path
source = Path(sys.argv[1])
expected = {
    "pyproject.toml": "c4f46ef838505c60c2af4b844b73854504504d67802516d699210b5ccb24bc2c",
    "uv.lock": "7878442fa0b732e5cb51bad5cb8c8b76b4e4e1e54ae0099887981401ba1f9748",
    "package-lock.json": "6965ae1e1d1354557abc26bb3fb17d84e783673be21640bd03f5e5e10b4990d7",
}
for name, digest in expected.items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest, name
project = tomllib.loads((source / "pyproject.toml").read_text())["project"]
assert project["version"] == importlib.metadata.version("hermes-agent") == "0.21.2"
assert project["requires-python"] == ">=3.11,<3.14"
assert sys.version_info[:2] == (3, 13)
engines = json.loads((source / "package.json").read_text())["engines"]
assert engines == {"node": "^22.22.0 || ^24.11.0 || >=26.0.0",
                   "npm": "<11.10.0 || >=11.17.0"}
assert sqlite3.sqlite_version_info >= (3, 51, 3), "SQLite WAL-reset fix required"
with sqlite3.connect(":memory:") as db:
    db.execute("CREATE VIRTUAL TABLE probe USING fts5(text, tokenize='trigram')")
    db.execute("INSERT INTO probe VALUES ('synthetic foundation baseline')")
    assert db.execute("SELECT count(*) FROM probe WHERE probe MATCH 'baseline'").fetchone()[0] == 1
print("PASS NAS source fingerprints, installed package/support range, SQLite " +
      sqlite3.sqlite_version + " WAL-reset floor and FTS5 trigram")
'''
    result = command([metadata["python"], "-I", "-c", probe, metadata["source"]],
                     env=metadata["environment"])
    assert result.returncode == 0, result.stderr[-500:]
    print(result.stdout.strip())
    print("PASS native closure: no container runtime or workstation agent dependency")
    if capabilities:
        result = user_service(metadata, ["capability-check"])
        capability_log = state / "logs/capability-check.log"
        capability_log.write_text(result.stdout + result.stderr)
        capability_log.chmod(0o600)
        assert result.returncode == 0, "Offline check failed; inspect private log " + str(capability_log)
        assert "SKIPPED external vault task parity" in result.stdout
        assert "INACTIVE" in result.stdout
        print(result.stdout.strip())
        if options.vault_sources is not None:
            assert options.private_skills is not None
            result = user_service(metadata, [], operator=[metadata["python"], "-I",
                str(ROOT / "tests/hermes-native-vault.py"), "--metadata", str(meta_path.resolve()),
                "--sources", str(options.vault_sources), "--private-skills", str(options.private_skills)])
            log = state / "logs/installed-task-fixtures-758.log"
            log.write_text(result.stdout + result.stderr);log.chmod(0o600)
            assert result.returncode == 0, "Installed actual task fixtures failed; inspect private log " + str(log)
            print(result.stdout.strip())
            print("PASS actual installed task fixtures in transient user service matching installed environment")
    print("Installed generation: " + str(generation))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--vault-sources", type=Path)
    parser.add_argument("--private-skills", type=Path)
    args = parser.parse_args()
    assert (args.vault_sources is None) == (args.private_skills is None)
    assert args.vault_sources is None or args.installed
    source_checks()
    if args.installed:
        installed_checks(args)


if __name__ == "__main__":
    main()
