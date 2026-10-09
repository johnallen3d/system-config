# Omarchy temporary-file quotas

Resolved operationally in [Fizzy #732](https://app.fizzy.do/6284043/cards/732),
discovered during [#726](https://app.fizzy.do/6284043/cards/726).
Omarchy is Arch Linux with standalone Home Manager, not NixOS. Its native `/tmp`
mount policy is not managed by this repository.

## Why free space can coexist with failed writes

Omarchy's `/tmp` is tmpfs mounted with `usrquota`. A write can fail with
`EDQUOT` ("Disk quota exceeded") while `df` still reports globally available
space. Check the effective quota for the writing user, not just mount capacity.
On 2026-10-09, the effective soft and hard block limits for `johna` were both
6,444,758 KiB (about 6.15 GiB), against a 7.68 GiB mount. There was no per-user
inode limit. These are observed values, not a policy to impose on other hosts.

Run diagnostics as `johna`, using Bash explicitly over SSH:

```bash
ssh johna@omarchy 'bash -s' <<'BASH'
findmnt /tmp
df -h /tmp "$HOME"
df -i /tmp
du -x -h --max-depth=1 /tmp 2>/dev/null | sort -h | tail -20
BASH
```

The host did not have `quota`/`repquota` installed. This read-only Python probe
uses `quotactl_fd(Q_GETQUOTA)` for the caller's own UID, without sudo or additional
packages. Omarchy's Nix Python lacks the glibc wrapper, so the probe falls back to
the Linux x86-64 syscall; it does not assume that number on other architectures:

```python
import ctypes
import os
import platform

class Dqblk(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "bhardlimit", "bsoftlimit", "curspace", "ihardlimit", "isoftlimit",
        "curinodes", "btime", "itime",
    )] + [("valid", ctypes.c_uint32)]

libc = ctypes.CDLL(None, use_errno=True)
fd = os.open("/tmp", os.O_RDONLY | os.O_DIRECTORY)
try:
    quota = Dqblk()
    if hasattr(libc, "quotactl_fd"):
        libc.quotactl_fd.argtypes = [
            ctypes.c_int, ctypes.c_uint, ctypes.c_int, ctypes.c_void_p,
        ]
        result = libc.quotactl_fd(
            fd, 0x800007 << 8, os.getuid(), ctypes.byref(quota),
        )
    elif platform.machine() == "x86_64":
        libc.syscall.restype = ctypes.c_long
        result = libc.syscall(
            ctypes.c_long(443), ctypes.c_int(fd), ctypes.c_uint(0x800007 << 8),
            ctypes.c_int(os.getuid()), ctypes.byref(quota),
        )
    else:
        raise RuntimeError("quotactl_fd wrapper unavailable on this architecture")
    if result:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    print("Used bytes:", quota.curspace)
    print("Soft/hard KiB:", quota.bsoftlimit, quota.bhardlimit)
    print("Used inodes:", quota.curinodes)
    print("Soft/hard inode limits:", quota.isoftlimit, quota.ihardlimit)
finally:
    os.close(fd)
```

## Safe recovery

1. Identify large directories and inspect their ownership and newest file
   timestamps. Do not assume that a `cargo-install*` or target directory is stale
   based on its name alone.
2. Check for running Cargo/rustc/build processes and references to candidate
   directories in process command lines, working directories, open descriptors,
   and mapped files. `/proc` inspection may be restricted even for some same-user
   service processes; report that limitation, and do not treat an inaccessible
   build process as idle. Coordinate with the build owner when uncertain.
3. Move only confirmed idle, user-owned artifacts to a timestamped directory
   beneath `~/.cache`, after checking home filesystem capacity. A cross-filesystem
   move copies data before removing its source; do not move active build output.
   Retain the archive rather than deleting potentially useful build artifacts.
4. Re-read the user quota and verify ordinary file writes, Python stdout
   redirection, and a small SCP upload. Clean up only the probe files you created.

At investigation time, the previously reported 4.9 GiB
`/tmp/calc-enum-table-columns-target` directory was already absent and small
writes already worked; this session did not remove it. Four idle Cargo install
build directories were then archived to:

```text
/home/johna/.cache/tmp-quota-732/20261009T224910Z/
```

That reclaimed roughly 1.07 GiB of tmpfs allocations, leaving `/tmp` at about
209 MiB used. No mount/quota policy was changed and no active agents, servers, or
builds were restarted. The archive remains available for recovery or later
owner-approved deletion.

## Keep large builds off tmpfs

Prefer a project-specific target directory on the home filesystem for large Rust
builds. For a one-off work-project build, use command-scoped variables and an
explicit mise context (replace the project path below):

```bash
# Run in Bash; do not export these globally into existing agents.
project="$HOME/dev/src/amfaro/your-project"
mkdir -p "$HOME/.cache/build-tmp"
tmpdir=$(mktemp -d "$HOME/.cache/build-tmp/job.XXXXXXXX")
mise -C "$project" exec -- env \
  TMPDIR="$tmpdir" CARGO_TARGET_DIR="$project/target" cargo build
```

For `cargo install`, use its explicit `--target-dir` with a home-cache directory,
and scope `TMPDIR` to that command as above. Inspect leftovers after the command
finishes; do not automatically remove failed-build output or share scratch
folders between active jobs. This guidance does not change `PI_CODING_AGENT_DIR`,
`CLAUDE_CONFIG_DIR`, the native desktop, or the host's mount/quota configuration.
