#!/usr/bin/env python3
"""Real standalone HM metadata evaluation; never activate or touch live state.

Run with --source pointing to the intended Omarchy source snapshot. Temporary
copies preserve the real flake/fixture layout, including any snapshot assets.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def evaluate(root):
    expr = f'''let
      flake = builtins.getFlake {json.dumps('path:' + str(root))};
      cfg = flake.homeConfigurations."johna@omarchy".config;
    in {{
      metadata = builtins.fromJSON (builtins.unsafeDiscardStringContext cfg.xdg.configFile."hermes-native/production.json".text);
      execStart = cfg.systemd.user.services.hermes-production.Service.ExecStart;
      preflightBefore = cfg.home.activation.hermesNativeLifecycleCheck.before;
    }}'''
    result = subprocess.run(['nix', 'eval', '--impure', '--json', '--no-write-lock-file',
                             '--expr', expr], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='hermes771-nix-') as temporary:
        root = Path(temporary) / 'snapshot'
        shutil.copytree(args.source.resolve(), root, symlinks=True,
                        ignore=shutil.ignore_patterns('.git', '.worktrees', 'result', 'result-*'))
        baseline = evaluate(root)
        assert 'writeBoundary' in baseline['preflightBefore']
        metadata = baseline['metadata']
        assets = Path(metadata['managedAssets'])
        fixture = Path(metadata['productionFixture'])
        assert assets.is_relative_to('/nix/store')
        assert fixture.parent.parent / 'modules/home-manager/hermes-native' == assets
        assert fixture.with_name('hermes-native-production-state.py').is_file()
        assert Path(metadata['writerFixture']).is_file()
        for name in assets.rglob('*'):
            if name.is_file():
                assert name.read_bytes() == (root / 'modules/home-manager/hermes-native' /
                                             name.relative_to(assets)).read_bytes()
        unrelated = root / 'README.md'
        unrelated.write_bytes(unrelated.read_bytes() + b'\nSynthetic unrelated #771 update.\n')
        assert evaluate(root) == baseline, 'unrelated source changed production identity/unit'
        print('PASS unrelated flake update preserves exact metadata and ExecStart')
        asset = root / 'modules/home-manager/hermes-native/morning-brief.sh'
        original = asset.read_bytes()
        asset.write_bytes(original + b'\n# SYNTHETIC semantic asset mutation\n')
        changed = evaluate(root)
        assert changed['metadata'] != metadata and changed['execStart'] != baseline['execStart']
        asset.write_bytes(original)
        assert evaluate(root) == baseline, 'byte-equivalent restore changed identity'
        print('PASS real asset changes retain exact approval gates; byte-equivalent restore is stable')
        fixture_source = root / 'tests/hermes-native-production-state.py'
        fixture_source.write_bytes(fixture_source.read_bytes() + b'\n# SYNTHETIC fixture mutation\n')
        assert evaluate(root)['metadata'] != metadata, 'fixture change escaped approval identity'
        print('PASS installed relative fixture layout and fixture-change identity gate')


if __name__ == '__main__':
    main()
