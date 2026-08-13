# re-gdb

MCP server wrapping [GDB](https://www.gnu.org/software/gdb/) + [GEF](https://github.com/hugsy/gef) for dynamic analysis. Spawns a persistent GDB subprocess per session and drives it via the GDB/MI protocol.

## Tools

| Tool | What it does |
|---|---|
| `check_gdb` | Confirm gdb + GEF |
| `start_session` | Open a session, optionally load a binary |
| `end_session` | Tear down a session |
| `run_to_breakpoint` | Set a BP and run |
| `step_count` | Single-step N times, return registers |
| `read_memory` | `x/N fmt ADDR` |
| `gef_heap` | GEF `heap chunks` |
| `gef_canary` | GEF `canary` |
| `gef_registers` | GEF `registers` |
| `gef_vmmap` | GEF `vmmap` |
| `gef_nearpc` | GEF `nearpc` |
| `gef_pattern_create` / `gef_pattern_offset` | Cyclic-pattern helpers |
| `attach_pid` | Attach to a running process |

## Install

```bash
# System dependency
apt install gdb        # Debian/Ubuntu
brew install gdb        # macOS
scoop install gdb       # Windows

# GEF (auto-installed by install.sh to ~/.gdb/gef.py)
curl -fsSL https://github.com/hugsy/gef/raw/main/gef.py -o ~/.gdb/gef.py

# Python
pip install -e ./servers/re-gdb
```

## Safety

Never run unsigned binaries on a host you care about. Use a sandbox, a VM, or a Docker container. Dynamic analysis on untrusted samples is dangerous.
