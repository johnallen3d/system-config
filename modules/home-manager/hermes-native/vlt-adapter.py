"""Normal vault CLI access, confined to note content and the shared writer protocol.

Execute the installed vlt binary, not a shell or user-owned task. Real notes are
read-only in its sandbox; exact note postimages are committed by the supervisor.
"""
from pathlib import Path
import os
import subprocess
import tempfile

WRITES = {
    'create': {'name', 'path', 'content', 'silent', 'timestamps'},
    'append': {'file', 'content', 'timestamps'},
    'prepend': {'file', 'content', 'timestamps'},
    'write': {'file', 'content', 'timestamps'},
    'patch': {'file', 'heading', 'line', 'content', 'delete', 'old', 'new', 'timestamps'},
    'property:set': {'file', 'name', 'value'},
    'property:remove': {'file', 'name'},
}
READS = {
    'read': {'file', 'heading', 'follow', 'backlinks'},
    'properties': {'file'}, 'backlinks': {'file'}, 'links': {'file'},
    'uri': {'file', 'heading', 'block'}, 'files': {'folder', 'ext', 'total'},
    'search': {'query', 'regex', 'context'}, 'tags': {'sort', 'counts'},
    'tag': {'tag'}, 'tasks': {'file', 'path', 'done', 'pending'},
    'orphans': set(), 'unresolved': set(), 'templates': set(),
}
FLAGS = {'silent', 'timestamps', 'delete', 'follow', 'backlinks', 'total', 'counts', 'done', 'pending'}
FORMATS = {'--json', '--yaml', '--csv', '--tsv', '--tree'}


def parse(r, args):
    r.p.require(isinstance(args, list) and len(args) <= 32
                and all(isinstance(a, str) and len(a) <= 262144 and '\x00' not in a for a in args),
                'bounded vault command required')
    # Personal is the only mounted vault. No path/env-based alternate target.
    args = list(args)
    if args and args[0].startswith('vault='):
        r.p.require(args.pop(0) == 'vault=Personal', 'only the Personal vault is available')
    r.p.require(args and args[0] in WRITES.keys() | READS.keys(),
                'unsupported vlt command; use note create/write/append/prepend/patch/property or vault reads')
    action = args.pop(0)
    allowed = (WRITES | READS)[action]
    options = {}
    for arg in args:
        if arg in FORMATS:
            continue
        key, sep, value = arg.partition('=')
        r.p.require(key in allowed and key not in options, 'unknown or duplicate vlt option')
        r.p.require((key in FLAGS and not sep) or (key not in FLAGS and sep), 'vlt option needs its value')
        options[key] = value if sep else True
    if action in WRITES:
        r.p.require('path' in options and 'name' in options if action == 'create' else 'file' in options,
                    'explicit note target required')
        if action in {'create', 'append', 'prepend', 'write'}:
            r.p.require('content' in options, 'provide content= explicitly; shell/stdin execution is unnecessary')
        if action == 'patch':
            r.p.require('content' in options or 'delete' in options or {'old', 'new'} <= options.keys(),
                        'patch needs content=, delete, or old=/new=')
        if action.startswith('property:'):
            r.p.require('name' in options and (action != 'property:set' or 'value' in options),
                        'property name/value required')
    for key in {'file', 'path', 'folder'} & options.keys():
        r.p.relative(options[key])
        r.p.require(options[key] and not any(p.startswith('.') for p in Path(options[key]).parts),
                    'vault content paths only; no hidden/config paths')
    return action, options, ['vault=Personal', action, *args]


def note_target(r, vault, action, options):
    """Resolve vlt title lookup once and pass an unambiguous relative file path."""
    if action == 'create':
        name = options['path']
        if not name.endswith('.md'):
            name += '.md'
        r.p.relative(name)
        r.p.require(not any(q.startswith('.') for q in Path(name).parts), 'note content paths only')
        r.p.stage.safe(vault / name, missing=True, owner=os.getuid() if (vault / name).exists() else None)
        r.p.require(not (vault / name).exists(), 'note already exists; use write/append/patch instead')
        return name
    name = options['file']
    exact = vault / (name if name.endswith('.md') else name + '.md')
    if exact.is_file():
        r.p.stage.safe(exact, owner=os.getuid())
        return exact.relative_to(vault).as_posix()
    r.p.require('/' not in name, 'note path not found')
    title = name[:-3] if name.endswith('.md') else name
    matches = [p for p in vault.rglob('*.md') if p.stem == title
               and not any(q.startswith('.') for q in p.relative_to(vault).parts)]
    r.p.require(len(matches) == 1, 'note title missing or ambiguous; provide its relative path')
    r.p.stage.safe(matches[0], owner=os.getuid())
    return matches[0].relative_to(vault).as_posix()


def run(r, m, args, *, observer, scan):
    action, options, argv = parse(r, args)
    writing = action in WRITES
    owner = r.live_owner(m, 'vaultWrites' if writing else 'poller')
    r.p.require(owner['phase'] == 'NATIVE_LIVE', 'normal vault access requires live native ownership')
    state, vault = Path(m['paths']['state']), Path(m['vault'])
    binary = next((Path(p) / 'vlt' for p in m['environment']['PATH'].split(':')
                   if (Path(p) / 'vlt').is_file()), None)
    r.p.require(binary is not None and str(binary).startswith('/nix/store/'), 'installed pinned vlt required')
    target = note_target(r, vault, action, options) if writing else None
    if writing and action != 'create':
        # vlt 0.11 interprets a bare Root.md as a title and appends .md again.
        # An explicit ./ path also prevents duplicate-title index selection.
        argv = [f'file=./{target}' if a.startswith('file=') else a for a in argv]
    elif not writing and 'file' in options and '/' not in options['file'] and options['file'].endswith('.md'):
        argv = [f"file=./{options['file']}" if a.startswith('file=') else a for a in argv]
    runs = state / 'controller/vlt-runs'
    r.p.stage.mkdir(runs)
    run = Path(tempfile.mkdtemp(prefix='vlt-', dir=runs)); run.chmod(0o700)
    env = {k: v for k, v in m['environment'].items()
           if not k.startswith(('PI_', 'CLAUDE_', 'HERMES_PRODUCTION_'))
           and not k.endswith(('TOKEN', 'API_KEY'))}
    alias = str(state / 'workspace/notes')
    env.update(HOME='/tmp/vlt-home', XDG_CONFIG_HOME='/tmp/vlt-config', XDG_CACHE_HOME='/tmp/vlt-cache',
               XDG_DATA_HOME='/tmp/vlt-data', XDG_STATE_HOME='/tmp/vlt-state',
               VAULT_DIR=alias, VLT_VAULT_PATH=alias, VLT_VAULT='Personal')
    command = [m['bubblewrap'], '--unshare-all', '--die-with-parent', '--new-session',
               '--ro-bind', '/nix/store', '/nix/store', '--proc', '/proc', '--dev', '/dev',
               '--tmpfs', '/tmp', '--tmpfs', '/home', '--dir', '/etc',
               '--ro-bind', str(vault), '/vault-source', '--tmpfs', alias]
    # vlt's locks/index are private bookkeeping, never a second real-vault writer.
    for entry in sorted(vault.iterdir()):
        if entry.name in {'.vlt', '.vlt.lock', '.obsidian', 'CLAUDE.md'}:
            continue
        r.p.stage.safe(entry, directory=entry.is_dir(), owner=os.getuid())
        command += ['--ro-bind', str(entry), alias + '/' + entry.name]
    index = run / 'obsidian'; r.p.stage.mkdir(index)
    app = vault / '.obsidian/app.json'
    r.p.stage.atomic(index / 'app.json', r.p.stage.read_private(app, owner=os.getuid()) if app.exists() else b'{}\n')
    command += ['--bind', str(index), alias + '/.obsidian']

    def execute(reservation=None):
        cmd = list(command)
        output_path = None
        if writing:
            # Replace the closest existing parent with a sparse private overlay.
            # Non-target siblings are read-only mounts; new subfolders are private.
            parent = (vault / target).parent
            while not parent.exists():
                parent = parent.parent
            r.p.stage.safe(parent, directory=True, owner=os.getuid())
            relative = parent.relative_to(vault)
            overlay = run / 'overlay'; r.p.stage.mkdir(overlay)
            local = (vault / target).relative_to(parent)
            output_path = overlay / local
            output_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if reservation.expected[target] is not None:
                r.p.stage.atomic(output_path, r.p.stage.read_private(vault / target, owner=os.getuid()))
            mount = alias if relative == Path('.') else alias + '/' + relative.as_posix()
            cmd += ['--bind', str(overlay), mount]
            for sibling in sorted(parent.iterdir()):
                if sibling.name == local.parts[0] or sibling.name in {'.vlt', '.vlt.lock', '.obsidian', 'CLAUDE.md'}:
                    continue
                r.p.stage.safe(sibling, directory=sibling.is_dir(), owner=os.getuid())
                stub = overlay / sibling.name
                if sibling.is_dir(): r.p.stage.mkdir(stub)
                else: r.p.stage.atomic(stub, b'')
                cmd += ['--ro-bind', str(sibling), mount + '/' + sibling.name]
            if parent == vault:
                cmd += ['--bind', str(index), alias + '/.obsidian']
            reservation.check()
        result = subprocess.run([*cmd, '--chdir', alias, str(binary), *argv], env=env,
                                capture_output=True, timeout=60, cwd='/', stdin=subprocess.DEVNULL)
        r.p.stage.atomic(run / 'stdout', result.stdout); r.p.stage.atomic(run / 'stderr', result.stderr)
        r.p.require(len(result.stdout) <= 262144, 'bounded vault command output')
        if writing:
            reservation.check()
            if result.returncode == 0:
                data = r.p.stage.read_private(output_path, owner=os.getuid())
                r.p.require(len(data) <= 4 * 1024 * 1024, 'bounded note postimage')
                r.p.atomic_durable(vault / target, data, reservation.expected[target])
                r.p.require(r.p.stage.read_private(vault / target, owner=os.getuid()) == data, 'note postimage readback')
                scan((target,))
            # A rejected vlt edit has no real-vault effects. Complete its unchanged
            # reservation, rather than killing the gateway for an ordinary error.
            reservation.complete(r.writer_module().manifest(vault, (target,)))
        return result

    if writing:
        with r.writer_module().normal_reserve(state, vault, (target,), observer=observer) as reservation:
            result = execute(reservation)
    else:
        result = execute()
    r.p.stage.atomic(run / 'receipt.json', r.p.stage.encoded({
        'status': 'COMPLETE' if result.returncode == 0 else 'NO_VAULT_CHANGE',
        'command': action, 'target': target, 'realVaultInChild': 'READ_ONLY', 'retentionDaysMinimum': 14}))
    r.p.require(result.returncode == 0, 'vlt command failed; no vault change; diagnostics retained privately')
    return result.stdout
