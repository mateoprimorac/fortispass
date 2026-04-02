"""
server.py — fortispass server launcher.

  1. Generates .env if missing
  2. First-time Google Drive backup setup (asked once, never again)
  3. Runs an immediate backup on start (if configured)
  4. Builds and starts Docker
  5. Shows a live dashboard (refreshes every 60 seconds)

Usage:
  python server.py                   # start with default 4h backup interval
  python server.py --interval 2      # start with 2h backup interval (1–48)

Other tools (run from project root):
  python tools/stop.py               # stop server, keep data
  python tools/stop.py --wipe        # stop server and delete all data
  python tools/restore.py            # restore from Google Drive backup
  python tools/backup.py             # configure backups
"""

import base64
import os
import platform
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

# -- Dependency check + auto-install ------------------------------------------
_REQUIRED = [
    # (import_name,  pip_package_name)
    ("nacl",              "PyNaCl"),
    ("cryptography",      "cryptography"),
    ("google.oauth2",     "google-auth"),
    ("googleapiclient",   "google-api-python-client"),
    ("httplib2",          "google-auth-httplib2"),
]

def _ensure_deps():
    missing = []
    for import_name, pip_name in _REQUIRED:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        return

    if platform.system() == "Windows":
        os.system("color")

    print(f"\n  Installing {len(missing)} missing package(s): {', '.join(missing)}\n")
    pip = [sys.executable, "-m", "pip", "install", "--quiet"] + missing
    result = subprocess.run(pip)
    if result.returncode != 0:
        print(f"\n  ERROR: pip install failed. Try running manually:\n")
        print(f"    pip install {' '.join(missing)}\n")
        sys.exit(1)

    # Re-check after install — exit if anything still missing
    still_missing = []
    for import_name, pip_name in _REQUIRED:
        try:
            __import__(import_name)
        except ImportError:
            still_missing.append(pip_name)
    if still_missing:
        print(f"\n  ERROR: Could not import after install: {', '.join(still_missing)}")
        print(f"  Try running:  pip install {' '.join(still_missing)}\n")
        sys.exit(1)

    print(f"  All packages ready.\n")

_ensure_deps()
import nacl.signing  # now safe to import at module level

# -- Early console helpers used by top-level flag handlers ---------------------
def _early_clr():
    if not is_interactive_terminal():
        return
    try:
        os.system("cls" if platform.system() == "Windows" else "clear")
    except Exception:
        pass


def set_terminal_title(title: str):
    if not is_interactive_terminal():
        return
    safe_title = title.replace("\x1b", "")
    try:
        if platform.system() == "Windows":
            os.system(f"title {safe_title}")
        else:
            sys.stdout.write(f"\33]0;{safe_title}\a")
            sys.stdout.flush()
    except Exception:
        pass


def restore_terminal_state():
    if not is_interactive_terminal():
        return
    try:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
    except Exception:
        pass


def is_interactive_terminal() -> bool:
    try:
        return bool(sys.stdin and sys.stdin.isatty() and sys.stdout and sys.stdout.isatty())
    except Exception:
        return False


def _early_run(cmd, check=True, quiet=False):
    kwargs = {
        "shell": True,
        "cwd": str(Path(__file__).parent.resolve()),
        "check": check,
    }
    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    return subprocess.run(cmd, **kwargs)


def windows_parent_process_name() -> str | None:
    if platform.system() != "Windows":
        return None
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {os.getppid()}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        if not line or line.startswith("INFO:"):
            return None
        match = re.match(r'"([^"]+)"', line)
        if not match:
            return None
        return match.group(1).lower()
    except Exception:
        return None


def launched_from_shell() -> bool:
    if platform.system() != "Windows":
        return True
    parent = windows_parent_process_name()
    if not parent:
        return True
    return parent in {
        "cmd.exe",
        "powershell.exe",
        "pwsh.exe",
        "bash.exe",
        "wsl.exe",
        "sh.exe",
    }


def handoff_to_interactive_shell(access_value: str):
    if platform.system() != "Windows":
        return
    if not is_interactive_terminal():
        return
    if launched_from_shell():
        return

    shell = os.environ.get("COMSPEC") or "cmd.exe"
    try:
        subprocess.run([shell, "/K", "title fortispass"], cwd=str(HERE), check=False)
    except Exception:
        pass


set_terminal_title("fortispass")


class SetupAnimation:
    def __init__(self, message: str = "setting up server"):
        self._message = message
        self._detail = ""
        self._last_detail = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._rendered = False
        self._interactive = is_interactive_terminal()

    def start(self, detail: str = ""):
        with self._lock:
            self._detail = detail
        if not self._interactive:
            self._render_fallback(detail)
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="setup-animation")
        self._thread.start()

    def update(self, detail: str):
        with self._lock:
            self._detail = detail
        if not self._interactive:
            self._render_fallback(detail)

    def stop(self):
        if not self._interactive:
            return
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.3)
        if self._rendered:
            # Remove the transient block cleanly without touching the ASCII art.
            # The animation renders 2 spacer lines, 1 message line, and 1 detail line.
            try:
                sys.stdout.write("\033[4F")
                for _ in range(4):
                    sys.stdout.write("\r\033[2K\n")
                restore_terminal_state()
            except Exception:
                pass
            self._rendered = False
            self._last_detail = None
        self._thread = None

    def _run(self):
        step = 0
        try:
            self._render_static_frame()
            while not self._stop.is_set():
                with self._lock:
                    detail = self._detail

                self._render_status(step, detail)

                step += 1
                if self._stop.wait(0.12):
                    break
        except Exception:
            self._interactive = False
            self._rendered = False
            restore_terminal_state()

    def _render_static_frame(self):
        _early_clr()
        sys.stdout.write("\033[?25l")
        sys.stdout.write(ASCII_ART + "\n\n\n")
        sys.stdout.write(f"           {WHITE}{self._message}{RESET}\n")
        sys.stdout.write("  \n")
        sys.stdout.flush()
        self._rendered = True
        self._last_detail = ""

    def _render_status(self, step: int, detail: str):
        sys.stdout.write("\033[2F")
        sys.stdout.write("\r")
        sys.stdout.write(self._render_message(step))
        sys.stdout.write("\n")
        if detail != self._last_detail:
            sys.stdout.write("\r\033[2K")
            if detail:
                sys.stdout.write(f"  {DIM}{detail}{RESET}\n")
            else:
                sys.stdout.write("\n")
            self._last_detail = detail
        else:
            sys.stdout.write("\n")
        sys.stdout.flush()

    def _render_message(self, step: int) -> str:
        spinner_frames = [
            f"{WHITE}{BOLD}●{RESET} {DIM}● ●{RESET}",
            f"{DIM}●{RESET} {WHITE}{BOLD}●{RESET} {DIM}●{RESET}",
            f"{DIM}● ●{RESET} {WHITE}{BOLD}●{RESET}",
        ]
        spinner = spinner_frames[(step // 4) % len(spinner_frames)]
        return f"  {spinner}"

    def _render_fallback(self, detail: str):
        status = detail or self._message
        if status == self._last_detail:
            return
        print(f"  {DIM}{status}{RESET}")
        self._last_detail = status


def print_docker_not_running_message():
    print(f"  {RED}{'=' * 54}{RESET}")
    print(f"  {RED}{BOLD}  Docker is not running or not installed.{RESET}")
    print(f"  {RED}{'=' * 54}{RESET}\n")
    print(f"  Fortispass runs inside Docker. To fix this:\n")
    print(f"  {BOLD}Windows / macOS:{RESET}")
    print(f"    1. Download Docker Desktop from  https://docker.com/products/docker-desktop")
    print(f"    2. Install and launch it")
    print(f"    3. Wait for the whale icon to appear in the system tray")
    print(f"    4. Run  python server.py  again\n")


def secure_delete_file(path: Path):
    """Best-effort overwrite-then-delete for small local secret files."""
    if not path.exists() or not path.is_file():
        return
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    size = path.stat().st_size
    if size > 0:
        chunk_size = 64 * 1024
        with path.open("r+b", buffering=0) as f:
            for pattern in ("random", "zeros"):
                f.seek(0)
                remaining = size
                while remaining > 0:
                    chunk_len = min(chunk_size, remaining)
                    if pattern == "random":
                        chunk = os.urandom(chunk_len)
                    else:
                        chunk = b"\x00" * chunk_len
                    f.write(chunk)
                    remaining -= chunk_len
                f.flush()
                os.fsync(f.fileno())
    path.unlink()
    print(f"  {BOLD}Linux:{RESET}")
    print(f"    1. Install Docker Engine:  https://docs.docker.com/engine/install/")
    print(f"    2. Start the service:      sudo systemctl start docker")
    print(f"    3. (Optional) add yourself to the docker group so you do not need sudo:")
    print(f"       sudo usermod -aG docker $USER   then log out and back in")
    print(f"    4. Run  python server.py  again\n")


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _pad_ansi(text: str, width: int) -> str:
    visible = len(_ANSI_RE.sub("", text))
    return text + (" " * max(0, width - visible))


def menu_line(num: str, command: str, desc: str, command_width: int = 31):
    print(f"  {BOLD}{num}.{RESET}  {_pad_ansi(command, command_width)}  {DIM}{desc}{RESET}")

# -- tools/ on path so `from backup import ...` works -------------------------
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).parent / 'tools'))

# -- ANSI colours --------------------------------------------------------------
if platform.system() == "Windows":
    os.system("color")
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"

# -- Paths ---------------------------------------------------------------------
HERE     = Path(__file__).parent.resolve()
ENV_PATH = HERE / ".env"
COMPOSE  = "docker compose -f docker-compose.yml -f docker-compose.local.yml"

# -- ASCII art ---------------------------------------------------------------
BLUE   = "\033[38;2;58;111;216m"   # #3A6FD8
WHITE  = "\033[38;2;255;255;255m"  # #FFFFFF
ASCII_ART = "\n".join([
    BLUE + " .o88o.                        .    o8o           " + WHITE + "                                       " + RESET,
    BLUE + " 888 `\"                      .o8    `\"'           " + WHITE + "                                       " + RESET,
    BLUE + "o888oo   .ooooo.  oooo d8b .o888oo oooo   .oooo.o " + WHITE + "oo.ooooo.   .oooo.    .oooo.o  .oooo.o " + RESET,
    BLUE + " 888    d88' `88b `888\"\"8P   888   `888  d88(  \"8 " + WHITE + " 888' `88b `P  )88b  d88(  \"8 d88(  \"8 " + RESET,
    BLUE + " 888    888   888  888       888    888  `\"Y88b.  " + WHITE + " 888   888  .oP\"888  `\"Y88b.  `\"Y88b.  " + RESET,
    BLUE + " 888    888   888  888       888 .  888  o.  )88b " + WHITE + " 888   888 d8(  888  o.  )88b o.  )88b " + RESET,
    BLUE + "o888o   `Y8bod8P' d888b      \"888\" o888o 8\"\"888P' " + WHITE + " 888bod8P' `Y888\"\"8o 8\"\"888P' 8\"\"888P' " + RESET,
    BLUE + "                                                  " + WHITE + " 888                                   " + RESET,
    BLUE + "                                                  " + WHITE + "o888o                                  " + RESET,
])


# -- Argument parsing ----------------------------------------------------------
import argparse as _ap

def _interactive_help():
    """Show help menu and let the user pick an action or just start the server."""
    if platform.system() == "Windows":
        os.system("color")
    clr = lambda: os.system("cls" if platform.system() == "Windows" else "clear")
    clr()

    print(ASCII_ART)
    print(f"  {BOLD}fortispass server — available flags{RESET}\n")
    menu_line("1", f"{GREEN}start{RESET}", "python server.py")
    menu_line("2", f"{GREEN}start --interval X{RESET}", "python server.py --interval X  (1-48h, default 4)")
    menu_line("3", f"{GREEN}start --port X{RESET}", "python server.py --port X  (default 8080)")
    menu_line("4", f"{GREEN}start --max-devices X{RESET}", "python server.py --max-devices X  (default 3)")
    menu_line("5", f"{YELLOW}--restore{RESET}", "restore the server from a Google Drive backup")
    menu_line("6", f"{YELLOW}--backup{RESET}", "configure or run a Google Drive backup")
    menu_line("7", f"{YELLOW}--stop{RESET}", "stop the server (data volumes preserved)")
    menu_line("8", f"{RED}--wipe{RESET}", "stop the server and permanently delete all data")
    print(f"\n  {DIM}{'─' * 46}{RESET}\n")
    choice = input(f"  Enter a number to run it: ").strip()
    print()
    if choice == "1":
        return "start"
    elif choice == "2":
        raw = input(f"  Interval in hours (1–48): ").strip()
        try:
            v = int(raw)
            if not (1 <= v <= 48):
                raise ValueError
            return f"start:{v}"
        except ValueError:
            print(f"  {RED}Invalid — must be 1–48. Starting with default 4h.{RESET}\n")
            return "start"
    elif choice == "3":
        raw = input(f"  Port number (1024–65535, default 8080): ").strip()
        try:
            v = int(raw)
            if not (1024 <= v <= 65535):
                raise ValueError
            return f"start:port:{v}"
        except ValueError:
            print(f"  {RED}Invalid — must be 1024–65535. Starting on default 8080.{RESET}\n")
            return "start"
    elif choice == "4":
        raw = input(f"  Max devices per vault (1–100, default 3): ").strip()
        try:
            v = int(raw)
            if not (1 <= v <= 100):
                raise ValueError
            return f"start:max-devices:{v}"
        except ValueError:
            print(f"  {RED}Invalid — must be 1–100. Starting with default 3.{RESET}\n")
            return "start"
    elif choice == "5":
        return "restore"
    elif choice == "6":
        return "backup"
    elif choice == "7":
        return "stop"
    elif choice == "8":
        return "wipe"
    else:
        print(f"  {DIM}Unrecognised choice. Nothing was started.{RESET}\n")
        return None

_parser = _ap.ArgumentParser(add_help=False)
_parser.add_argument('--interval',    type=int, default=None)
_parser.add_argument('--port',        type=int, default=None)
_parser.add_argument('--max-devices', type=int, default=None, dest='max_devices')
_parser.add_argument('--wipe',     action='store_true')
_parser.add_argument('--restore',  action='store_true')
_parser.add_argument('--backup',   action='store_true')
_parser.add_argument('--stop',     action='store_true')
_parser.add_argument('--help',     action='store_true')
_args, _ = _parser.parse_known_args()

if _args.help:
    _action = _interactive_help()
    if _action is None:
        _sys.exit(0)
    if _action == "restore":
        import importlib.util as _ilu_h
        _spec_h = _ilu_h.spec_from_file_location("restore", _pl.Path(__file__).parent / "tools" / "restore.py")
        _rm = _ilu_h.module_from_spec(_spec_h)
        _spec_h.loader.exec_module(_rm)
        _rm.main()
        _sys.exit(0)
    elif _action in ("backup", "stop", "wipe"):
        # Set the corresponding flag and fall through to the unified handlers below
        setattr(_args, _action, True)
    elif _action.startswith("start:port:"):
        _args.port = int(_action.split(":")[2])
    elif _action.startswith("start:max-devices:"):
        _args.max_devices = int(_action.split(":")[2])
    elif _action.startswith("start:"):
        _args.interval = int(_action.split(":")[1])
    # else: fall through to normal start

# Resolve port — CLI --port takes priority, then env LISTEN_PORT, then default 8080
_port: int = _args.port if _args.port is not None else int(os.environ.get("LISTEN_PORT", 8080))
# Resolve max devices — CLI/interactive takes priority, then env, then default 3
_max_devices: int = _args.max_devices if _args.max_devices is not None else int(os.environ.get("MAX_DEVICES_PER_VAULT", 3))

if _args.wipe:
    _clr = lambda: os.system("cls" if platform.system() == "Windows" else "clear")
    _clr()
    print(ASCII_ART + "\n")
    print(f"  {RED}{BOLD}{'=' * 54}{RESET}")
    print(f"  {RED}{BOLD}  DESTRUCTIVE OPERATION — READ CAREFULLY             {RESET}")
    print(f"  {RED}{BOLD}{'=' * 54}{RESET}\n")
    print(f"  {RED}This will permanently delete:{RESET}")
    print(f"  {RED}  •  The PostgreSQL database (all user vaults){RESET}")
    print(f"  {RED}  •  The Redis store (all active sessions){RESET}")
    print(f"  {RED}  •  All Docker volumes for this stack{RESET}\n")
    print(f"  {RED}This CANNOT be undone. There is no recovery unless you{RESET}")
    print(f"  {RED}have a Google Drive backup configured.{RESET}\n")
    for _remaining in range(10, 0, -1):
        print(f"  {DIM}Confirmation unlocks in {_remaining}s …{RESET}", end="\r", flush=True)
        time.sleep(1)
    print(" " * 60, end="\r")
    _ans = input(f"  Type  {BOLD}CONFIRM{RESET}  to wipe everything, or anything else to abort: ").strip()
    if _ans != "CONFIRM":
        print(f"\n  {DIM}Aborted — nothing was changed.{RESET}\n")
        _sys.exit(0)
    _anim = SetupAnimation("wiping server")
    _anim.start("removing containers and volumes")
    try:
        _early_run(f"{COMPOSE} down -v", quiet=True)
        secure_delete_file(HERE / ".env")
        secure_delete_file(HERE / ".backup_config.json")
        _anim.stop()
        _early_clr()
        print(ASCII_ART + "\n")
        print(f"\n  {GREEN}[OK]{RESET}  All containers and data volumes removed.")
        print(f"      Run  {BOLD}python server.py{RESET}  to start fresh.\n")
    except subprocess.CalledProcessError:
        _anim.stop()
        _early_clr()
        print(ASCII_ART + "\n")
        print(f"\n  {RED}Docker command failed. Make sure Docker Desktop is running and try again.{RESET}\n")
        _sys.exit(1)
    # Kill every other server.py process (dashboard loops, background instances).
    # Inline — no delegation to stop.py which calls sys.exit() and aborts this process.
    # Uses wmic on Windows (always available, no extra deps) and pkill -9 on Unix.
    _my_pid = os.getpid()
    if platform.system() == "Windows":
        _wmic_query = (
            'wmic process where '
            '"CommandLine like \'%server.py%\' '
            'and ProcessId != ' + str(_my_pid) + '" '
            'call terminate'
        )
        subprocess.run(
            _wmic_query,
            shell=True, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.run(
            f"pkill -9 -f server.py 2>/dev/null; true",
            shell=True, check=False,
        )
    _sys.exit(0)


if _args.restore:
    # Delegate entirely to tools/restore.py logic
    import importlib.util as _ilu2
    _spec2 = _ilu2.spec_from_file_location('restore', _pl.Path(__file__).parent / 'tools' / 'restore.py')
    _restore = _ilu2.module_from_spec(_spec2)
    _spec2.loader.exec_module(_restore)
    _restore.main()
    _sys.exit(0)

if _args.stop:
    _anim = SetupAnimation("stopping server")
    _anim.start("stopping containers")
    try:
        _early_run(f"{COMPOSE} down", quiet=True)
        _anim.stop()
        _early_clr()
        print(ASCII_ART + "\n")
        print(f"\n  {GREEN}[OK]{RESET}  Server stopped. Data volumes are intact.")
        print(f"      Run  {BOLD}python server.py{RESET}  to start again.\n")
    except subprocess.CalledProcessError:
        _anim.stop()
        _early_clr()
        print(ASCII_ART + "\n")
        print(f"\n  {RED}Docker command failed. Make sure Docker Desktop is running and try again.{RESET}\n")
        _sys.exit(1)
    _sys.exit(0)

if _args.backup:
    # Delegate to backup setup wizard in tools/backup.py
    import importlib.util as _ilu3
    _spec3 = _ilu3.spec_from_file_location('backup', _pl.Path(__file__).parent / 'tools' / 'backup.py')
    _bkmod = _ilu3.module_from_spec(_spec3)
    _spec3.loader.exec_module(_bkmod)
    _bkmod.setup_wizard(interval_hours=_args.interval or 4)
    _sys.exit(0)

if _args.interval is not None:
    if not (1 <= _args.interval <= 48):
        print(f'\n  ERROR: --interval must be between 1 and 48 hours (got {_args.interval}).\n')
        _sys.exit(1)
BACKUP_INTERVAL = _args.interval  # None = use stored config default (4h)



# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def clr():
    if not is_interactive_terminal():
        return
    try:
        os.system("cls" if platform.system() == "Windows" else "clear")
    except Exception:
        pass


def run(cmd, check=True, quiet=False):
    kwargs = {
        "shell": True,
        "cwd": str(HERE),
        "check": check,
    }
    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    return subprocess.run(cmd, **kwargs)


def run_out(cmd):
    r = subprocess.run(cmd, shell=True, cwd=str(HERE),
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def env_value(name: str, default: str | None = None) -> str | None:
    if not ENV_PATH.exists():
        return default
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            if key.strip() == name:
                return value.strip()
    return default


def deployment_mode() -> str:
    return env_value("DEPLOYMENT_MODE", "local") or "local"


def access_display(ip: str) -> tuple[str, str, str]:
    mode = deployment_mode()
    relay_url = (env_value("RELAY_URL", "") or "").strip()
    if mode == "production" and relay_url:
        return mode, "Public URL", relay_url
    return "local", "IP:Port", f"{ip}:{_port}"


def b64(b):
    return base64.b64encode(b).decode()


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unavailable"


def server_reachable(host: str = "localhost", port: int | None = None):
    """Try localhost first (always works for local Docker), then the LAN IP."""
    import urllib.request
    target_port = port if port is not None else _port
    for h in (["localhost", host] if host != "localhost" else ["localhost"]):
        try:
            urllib.request.urlopen(f"http://{h}:{target_port}/health", timeout=3)
            return True
        except Exception:
            continue
    return False


def other_server_client_running() -> bool:
    my_pid = os.getpid()
    if platform.system() == "Windows":
        query = (
            'wmic process where '
            f'"CommandLine like \'%server.py%\' and ProcessId != {my_pid}" '
            'get ProcessId /value'
        )
        out = run_out(query)
        return "ProcessId=" in out
    out = run_out(f"pgrep -f server.py | grep -v '^{my_pid}$'")
    return bool(out.strip())


def active_server_port() -> int:
    try:
        return int(env_value("LISTEN_PORT", str(_port)) or _port)
    except ValueError:
        return _port


def active_stack_running(port: int) -> bool:
    if server_reachable("localhost", port=port):
        return True
    state = run_out(f"{COMPOSE} ps --format '{{{{.Service}}}} {{{{.State}}}}'")
    if state:
        server_running = any(
            line.strip().startswith("server") and "running" in line.lower()
            for line in state.splitlines()
        )
        if server_running:
            return True
    return False


def terminate_other_server_clients() -> None:
    my_pid = os.getpid()
    if platform.system() == "Windows":
        query = (
            'wmic process where '
            '"CommandLine like \'%server.py%\' '
            'and ProcessId != ' + str(my_pid) + '" '
            'call terminate'
        )
        subprocess.run(
            query,
            shell=True,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    subprocess.run(
        f"pkill -9 -f 'server.py' 2>/dev/null || true",
        shell=True,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_running_server() -> bool:
    stop_anim = SetupAnimation("stopping server")
    stop_anim.start("stopping containers")
    try:
        _early_run(f"{COMPOSE} down", quiet=True)
        terminate_other_server_clients()
        return True
    except subprocess.CalledProcessError:
        return False
    finally:
        stop_anim.stop()


def get_uptime():
    cid = run_out(f"{COMPOSE} ps -q server")
    if not cid:
        return "—"
    started = run_out(
        f'docker inspect --format={{{{.State.StartedAt}}}} {cid.splitlines()[0]}'
    )
    if not started:
        return "—"
    try:
        t    = datetime.fromisoformat(started.replace("Z", "+00:00"))
        secs = int((datetime.now(timezone.utc) - t).total_seconds())

        days, rem  = divmod(secs, 86400)
        hours, rem = divmod(rem, 3600)
        mins       = rem // 60

        if days > 0:
            return f"{days}d {hours}h {mins:02d}min"
        elif hours > 0:
            return f"{hours}h {mins:02d}min"
        else:
            return f"{mins}min"
    except Exception:
        return "—"


# -----------------------------------------------------------------------------
# .env generation
# -----------------------------------------------------------------------------

def generate_env(ip: str = "localhost"):
    return generate_env_for_mode(ip, "local", f"http://{ip}:{_port}")


def generate_env_for_mode(ip: str, deployment_mode: str, relay_url: str):
    jwt_secret      = b64(secrets.token_bytes(32))
    server_hmac_key = b64(secrets.token_bytes(32))
    postgres_pw     = secrets.token_urlsafe(24)
    redis_pw        = secrets.token_urlsafe(24)
    signing_key     = nacl.signing.SigningKey.generate()
    sign_key_seed   = b64(bytes(signing_key))

    mode_label = "production/personal deployment" if deployment_mode == "production" else "local environment"
    contents = (
        f"# fortispass — {mode_label}\n"
        "# Generated by server.py — do NOT commit this file to git.\n\n"
        "LISTEN_HOST=0.0.0.0\n"
        f"LISTEN_PORT={_port}\n\n"
        f"DATABASE_URL=postgresql://fortispass:{postgres_pw}@postgres:5432/fortispass\n"
        f"POSTGRES_PASSWORD={postgres_pw}\n\n"
        f"REDIS_URL=redis://:{redis_pw}@redis:6379/0\n"
        f"REDIS_PASSWORD={redis_pw}\n\n"
        f"JWT_SECRET={jwt_secret}\n"
        f"SERVER_SIGN_KEY_SEED={sign_key_seed}\n"
        f"SERVER_HMAC_KEY={server_hmac_key}\n\n"
        "SELF_HOSTED=true\n"
        f"DEPLOYMENT_MODE={deployment_mode}\n"
        f"RELAY_URL={relay_url}\n"
        f"MAX_DEVICES_PER_VAULT={_max_devices}\n"
    )
    (HERE / ".env").write_text(contents)


def prompt_deployment_mode(ip: str) -> tuple[str, str]:
    clr()
    print(ASCII_ART + "\n")
    print(f"  {BOLD}Deployment Mode{RESET}\n")
    print(f"  {DIM}{'-' * 46}{RESET}\n")
    menu_line("1", f"{GREEN}Development / Testing{RESET}", "run locally on this machine / network")
    menu_line("2", f"{BLUE}Production / Personal{RESET}", "prepare for internet access with your own URL")
    print()

    while True:
        choice = input("  Enter a number: ").strip()
        if choice == "1":
            relay_url = f"http://{ip}:{_port}"
            return "local", relay_url
        if choice == "2":
            print()
            print(f"  {BOLD}Production / Personal deployment{RESET}\n")
            print(f"  {DIM}Fortispass will still run on this machine, but devices outside your{RESET}")
            print(f"  {DIM}local network need a public URL that points to it.{RESET}\n")
            print(f"  {DIM}Checklist:{RESET}")
            print(f"  {DIM}  1. Use a domain or dynamic DNS name that points to your public IP{RESET}")
            print(f"  {DIM}  2. Forward ports 80/443 or place the server behind a reverse proxy / VPS{RESET}")
            print(f"  {DIM}  3. Terminate TLS with HTTPS using nginx, Caddy, Traefik, or Let's Encrypt{RESET}")
            print(f"  {DIM}  4. Enter the final public base URL below so apps can connect from anywhere{RESET}\n")
            while True:
                raw = input("  Public relay URL (for example https://vault.example.com): ").strip()
                parsed = urllib.parse.urlparse(raw)
                if parsed.scheme not in ("http", "https") or not parsed.netloc:
                    print(f"  {YELLOW}Enter a full URL starting with http:// or https://{RESET}\n")
                    continue
                if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
                    print(f"  {YELLOW}Enter only the base URL, without extra path/query parts.{RESET}\n")
                    continue
                relay_url = raw.rstrip("/")
                print(f"\n  {GREEN}[OK]{RESET}  Using production/personal deployment mode.")
                print(f"  {DIM}Relay URL:{RESET} {relay_url}")
                print(f"  {DIM}Make sure this public URL reaches your server over the internet.{RESET}\n")
                input("  Press Enter to continue … ")
                return "production", relay_url
        print(f"  {YELLOW}Unrecognised choice. Nothing was started.{RESET}\n")


def patch_relay_url(ip: str, quiet: bool = False) -> None:
    """Keep RELAY_URL and LISTEN_PORT in an existing .env in sync.
    Called every startup so a --port flag or IP change takes effect without
    regenerating secrets. Docker Compose reads LISTEN_PORT from .env to set
    the host-side port mapping — if it's stale the health check polls the
    wrong port and the server appears unreachable."""
    import re
    text = ENV_PATH.read_text()
    changed = False
    deployment_mode = env_value("DEPLOYMENT_MODE", "local")

    # Update RELAY_URL to current IP + port
    if deployment_mode != "production":
        new_text = re.sub(
            r'^RELAY_URL=http://[^\s]+',
            f'RELAY_URL=http://{ip}:{_port}',
            text,
            flags=re.MULTILINE,
        )
        if new_text != text:
            changed = True
            text = new_text

    # Update LISTEN_PORT if it differs from the resolved port (e.g. --port flag)
    new_text = re.sub(
        r'^LISTEN_PORT=\d+',
        f'LISTEN_PORT={_port}',
        text,
        flags=re.MULTILINE,
    )
    if new_text != text:
        changed = True
        text = new_text

    # Update MAX_DEVICES_PER_VAULT if --max-devices was explicitly passed
    if _args.max_devices is not None:
        if re.search(r'^MAX_DEVICES_PER_VAULT=', text, re.MULTILINE):
            new_text = re.sub(
                r'^MAX_DEVICES_PER_VAULT=\d+',
                f'MAX_DEVICES_PER_VAULT={_max_devices}',
                text,
                flags=re.MULTILINE,
            )
        else:
            new_text = text.rstrip() + f'\nMAX_DEVICES_PER_VAULT={_max_devices}\n'
        if new_text != text:
            changed = True
            text = new_text

    if changed:
        ENV_PATH.write_text(text)
        if not quiet:
            parts = [f"LISTEN_PORT={_port}"]
            if deployment_mode != "production":
                parts.insert(0, f"RELAY_URL → http://{ip}:{_port}")
            if _args.max_devices is not None:
                parts.append(f"MAX_DEVICES_PER_VAULT={_max_devices}")
            print(f"  {YELLOW}[updated]{RESET}  {('  |  ').join(parts)}\n")


# -----------------------------------------------------------------------------
# Dashboard
# -----------------------------------------------------------------------------

def dot(ok):
    return f"{GREEN}*{RESET}" if ok else f"{RED}*{RESET}"


_STARTUP_BACKUP_SEEDED = [False]  # mutable so inner scope can write it


def get_container_stats():
    """Return (cpu_pct_str, ram_str) pulled live from docker stats."""
    cid = run_out(f"{COMPOSE} ps -q server")
    if not cid:
        return "—", "—"
    cid = cid.splitlines()[0]
    raw = run_out(
        f'docker stats --no-stream --format "{{{{.CPUPerc}}}}|{{{{.MemUsage}}}}" {cid}'
    )
    if not raw or "|" not in raw:
        return "—", "—"
    cpu, mem = raw.split("|", 1)
    # mem looks like "123MiB / 1.5GiB" — keep just the used part
    mem_used = mem.split("/")[0].strip() if "/" in mem else mem.strip()
    return cpu.strip(), mem_used


def build_dashboard_rows(ip, backup_enabled, startup_backup_time=None):
    healthy = server_reachable(ip)
    uptime  = get_uptime() if healthy else "—"
    _, access_label, access_value = access_display(ip)

    # Import backup module for last-backup string + interval
    last_backup_label = "Last backup"
    last_backup_value = f"{DIM}Not configured{RESET}"
    backup_interval_row = None  # (label, value) or None

    if backup_enabled:
        try:
            from backup import get_last_backup_str, load_config as _lcfg
            # If a startup backup just ran, use that time so we never show "Never"
            if startup_backup_time is not None and not _STARTUP_BACKUP_SEEDED[0]:
                import backup as _bkmod
                if _bkmod._last_backup_time is None:
                    _bkmod._last_backup_time = startup_backup_time
                _STARTUP_BACKUP_SEEDED[0] = True
            last_backup_value = get_last_backup_str()
            _cfg = _lcfg()
            _ival = BACKUP_INTERVAL or (_cfg.get("interval_hours", 4) if _cfg else 4)
            backup_interval_row = ("Backup every", f"{_ival}h")
        except Exception:
            last_backup_value = f"{DIM}Unavailable{RESET}"
    else:
        try:
            from backup import load_config
            cfg = load_config()
            if cfg is not None and not cfg.get("enabled"):
                last_backup_label = "[!]  No backup"
                last_backup_value = (
                    f"{YELLOW}Backups are disabled. If this server is lost,{RESET}\n"
                    f"  {'':14}  {YELLOW}all vaults are unrecoverable.{RESET}\n"
                    f"  {'':14}  {DIM}Run  python server.py --backup  to enable.{RESET}"
                )
        except Exception:
            pass

    cpu_pct, ram_used = get_container_stats() if healthy else ("—", "—")

    rows = [
        ("Server status",    f"{dot(healthy)}  {'Running' if healthy else 'Starting…'}"),
        ("Uptime",           uptime),
        ("CPU",              cpu_pct),
        ("RAM",              ram_used),
        (last_backup_label,  last_backup_value),
    ]
    if backup_interval_row:
        rows.append(backup_interval_row)
    rows.append((access_label, f"{WHITE}{access_value}{RESET}"))
    return rows


def render_dashboard(rows, ip: str):
    # Keep the previous panel on screen while fresh stats are loading, then
    # swap the whole dashboard once the new snapshot is ready.
    mode, _, access_value = access_display(ip)
    clr()
    print(ASCII_ART + "\n")
    print(f"  {DIM}{'-' * 46}{RESET}")

    for label, value in rows:
        print(f"  {BOLD}{label:<14}{RESET}  {value}")

    print(f"\n  {DIM}{'-' * 46}{RESET}")
    if mode == "production":
        print(f"  {DIM}Public URL should already point to this server.{RESET}")
        print(f"  {DIM}Keep HTTPS and your proxy/domain configuration in place.{RESET}")
    else:
        print(f"  {DIM}If connecting from another device, make sure{RESET}")
        print(f"  {DIM}port {_port} is allowed in your firewall.{RESET}")
    print(f"  {DIM}Ctrl+C to detach, server keeps running{RESET}")
    print(f"  {DIM}python server.py --stop  ·  python server.py --restore{RESET}\n")


def draw_dashboard(ip, backup_enabled, startup_backup_time=None):
    rows = build_dashboard_rows(ip, backup_enabled, startup_backup_time=startup_backup_time)
    render_dashboard(rows, ip)


def attach_to_dashboard(ip: str, backup_enabled: bool, show_opening_animation: bool = False):
    _, _, access_value = access_display(ip)
    set_terminal_title(f"fortispass ({access_value})")
    wait_anim = SetupAnimation("opening panel")
    first_rows = None
    try:
        if show_opening_animation:
            wait_anim.start("loading live stats")
        if not server_reachable(ip):
            if show_opening_animation:
                wait_anim.update("waiting for server")
            else:
                wait_anim.start("opening panel",)
                wait_anim.update("waiting for server")
            try:
                for _ in range(150):
                    if server_reachable(ip):
                        break
                    time.sleep(1)
                else:
                    wait_anim.stop()
                    clr()
                    print(ASCII_ART + "\n")
                    print(f"  {YELLOW}Fortispass is still starting.{RESET}")
                    print(f"  {DIM}The server has not answered yet at {access_value}.{RESET}\n")
                    return "unavailable"
            finally:
                pass
        elif show_opening_animation:
            time.sleep(0.2)
        first_rows = build_dashboard_rows(ip, backup_enabled, startup_backup_time=None)
        wait_anim.stop()
        render_dashboard(first_rows, ip)
        while True:
            if first_rows is not None:
                first_rows = None
            else:
                rows = build_dashboard_rows(ip, backup_enabled, startup_backup_time=None)
                render_dashboard(rows, ip)
            for _ in range(60):
                time.sleep(1)
    except KeyboardInterrupt:
        wait_anim.stop()
        restore_terminal_state()
        if is_interactive_terminal():
            try:
                sys.stdout.write("\r\033[2K")
                sys.stdout.flush()
            except Exception:
                pass
        return "detached"


def render_running_server_menu(ip: str, port: int, notice: str | None = None):
    clr()
    print(ASCII_ART + "\n")
    print(f"  {YELLOW}Fortispass is already running in the background.{RESET}\n")
    print(f"  {BOLD}IP:Port:{RESET} {WHITE}{ip}:{port}{RESET}\n")
    menu_line("1", f"{GREEN}Panel{RESET}", "attach to the running dashboard", command_width=8)
    menu_line("2", f"{YELLOW}Stop{RESET}", "stop the running server", command_width=8)
    menu_line("3", f"{DIM}Close{RESET}", "close this launcher", command_width=8)
    if notice:
        print(f"\n  {YELLOW}{notice}{RESET}")
    print()


def run_running_server_menu(ip: str, port: int):
    active_notice = None
    while True:
        render_running_server_menu(ip, port, active_notice)
        active_notice = None
        try:
            choice = input("  Enter a number: ").strip()
        except (EOFError, KeyboardInterrupt):
            active_notice = "Use Close to exit this launcher."
            restore_terminal_state()
            continue
        if choice == "1":
            backup_enabled = False
            try:
                from backup import load_config
                cfg = load_config()
                backup_enabled = bool(cfg and cfg.get("enabled"))
            except ImportError:
                pass
            result = attach_to_dashboard(ip, backup_enabled, show_opening_animation=True)
            if result == "detached":
                _, _, access_value = access_display(ip)
                print(f"\n  {DIM}Detached. Fortispass is still running at {access_value}.{RESET}")
                print(f"  {DIM}Run  python server.py  to reopen the live dashboard.{RESET}\n")
                handoff_to_interactive_shell(access_value)
            return
        if choice == "2":
            if stop_running_server():
                clr()
                print(ASCII_ART + "\n")
                print(f"  {GREEN}[OK]{RESET}  Server stopped. Run  {BOLD}python server.py{RESET}  to start again.\n")
            else:
                clr()
                print(ASCII_ART + "\n")
                print(f"  {RED}Docker command failed. Make sure Docker Desktop is running and try again.{RESET}\n")
            return
        if choice == "3":
            print(f"\n  {DIM}Closed.{RESET}\n")
            return
        active_notice = "Unrecognised choice. Nothing was started."


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    animation = SetupAnimation()
    interactive = is_interactive_terminal()
    backup_enabled = False
    ip = None
    try:
        set_terminal_title("fortispass")
        animation.start("checking Docker")

        # -- 0. Docker check -------------------------------------------------------
        # Verify Docker is installed and the daemon is running before doing anything.
        probe = subprocess.run(
            "docker info", shell=True, cwd=str(HERE),
            capture_output=True, text=True,
        )
        if probe.returncode != 0:
            animation.stop()
            print_docker_not_running_message()
            if interactive:
                input(f"  Press Enter to exit … ")
            sys.exit(1)

        running_port = active_server_port()
        if active_stack_running(running_port):
            animation.stop()
            running_ip = local_ip()
            if not interactive:
                _, _, access_value = access_display(running_ip)
                print(f"\n  {YELLOW}Fortispass is already running in the background.{RESET}")
                print(f"  {DIM}Access:{RESET} {access_value}\n")
                return
            run_running_server_menu(running_ip, running_port)
            return

        # Resolve IP early — needed for RELAY_URL which is baked into .env and
        # handed to the extension inside every QR payload and session create response.
        # localhost doesn't reach Docker on all machines, so we always use the LAN IP.
        ip = local_ip()

        # -- 1. Backup setup (asked once, stored in .backup_config.json) -----------
        try:
            from backup import is_configured, load_config, setup_wizard, run_backup, start_scheduler

            if not is_configured():
                if not interactive:
                    animation.stop()
                    print(ASCII_ART + "\n")
                    print(f"  {YELLOW}First-time backup setup requires an interactive terminal.{RESET}")
                    print(f"  {DIM}Run  python server.py  once in a normal terminal window to finish setup,{RESET}")
                    print(f"  {DIM}or configure .backup_config.json manually before launching detached.{RESET}\n")
                    sys.exit(1)
                animation.stop()
                clr()
                print(ASCII_ART + "\n")
                setup_wizard(interval_hours=BACKUP_INTERVAL or 4)
                animation.start("setting up server")

            cfg = load_config()
            if cfg and cfg.get("enabled"):
                backup_enabled = True

        except ImportError:
            pass

        # -- 2. .env / deployment mode --------------------------------------------
        animation.update("preparing environment")
        if ENV_PATH.exists():
            patch_relay_url(ip, quiet=True)   # keep local RELAY_URL in sync unless using production mode
        else:
            if not interactive:
                animation.stop()
                print(ASCII_ART + "\n")
                print(f"  {YELLOW}First-time environment setup requires an interactive terminal.{RESET}")
                print(f"  {DIM}Run  python server.py  once in a normal terminal window to choose deployment mode{RESET}")
                print(f"  {DIM}and generate .env, then detached launches will work normally.{RESET}\n")
                sys.exit(1)
            animation.stop()
            deployment_mode, relay_url = prompt_deployment_mode(ip)
            generate_env_for_mode(ip, deployment_mode, relay_url)
            animation.start("setting up server")

        # -- 3. Build + start Docker -----------------------------------------------
        animation.update("building and starting Docker")
        try:
            run(f"{COMPOSE} up --build -d", quiet=True)
        except subprocess.CalledProcessError:
            animation.stop()
            print_docker_not_running_message()
            if interactive:
                input(f"  Press Enter to exit … ")
            sys.exit(1)

        # -- 4. Wait for /health ---------------------------------------------------
        animation.update("waiting for server")
        for tick in range(150):  # 300s total — covers cold builds, image pulls, db init
            if server_reachable(ip):
                break

            if tick > 0 and tick % 5 == 0:
                state = run_out(
                    f"{COMPOSE} ps --format '{{{{.Service}}}} {{{{.State}}}}'"
                )
                # Crash detection — report immediately instead of waiting the full 300s
                for line in state.splitlines():
                    if line.strip().startswith("server") and "exit" in line.lower():
                        animation.stop()
                        print(f"\n\n  {RED}Server container crashed.{RESET} Showing logs:\n")
                        logs = run_out(f"{COMPOSE} logs --tail=60 server")
                        print(logs)

                        # ── Password mismatch auto-recovery ───────────────────
                        if "password authentication failed" in logs or "InvalidPasswordError" in logs:
                            print(f"\n  {YELLOW}Detected database password mismatch.{RESET}")
                            print(f"  This happens when the Postgres volume was initialised")
                            print(f"  with a different password than the one in your .env.")
                            print()
                            print(f"  {BOLD}Fix:{RESET} wipe the old volume and regenerate secrets,")
                            print(f"  then restart. {RED}All existing vault data will be lost.{RESET}")
                            if not interactive:
                                print()
                                print(f"  {DIM}Detached/non-interactive launch will not auto-confirm destructive recovery.{RESET}")
                                print(f"  {DIM}Run  python server.py  interactively, or run  python tools/stop.py --wipe{RESET}")
                                print(f"  {DIM}and then start again.{RESET}\n")
                                sys.exit(1)
                            print()
                            ans = input(f"  Type  {BOLD}CONFIRM{RESET}  to wipe and restart, or Enter to abort: ").strip()
                            if ans == "CONFIRM":
                                print(f"\n  Wiping volumes …", end=" ", flush=True)
                                run(f"{COMPOSE} down -v", check=False, quiet=True)
                                print(f"{GREEN}done{RESET}")
                                ENV_PATH.unlink(missing_ok=True)
                                print(f"  Regenerating secrets …", end=" ", flush=True)
                                generate_env(ip)
                                print(f"{GREEN}done{RESET}\n")
                                print(f"  Restarting …\n")
                                run(f"{COMPOSE} up --build -d", quiet=True)
                                animation.start("waiting for server")
                                for _ in range(90):
                                    if server_reachable(ip):
                                        break
                                    animation.update("waiting for server")
                                    time.sleep(2)
                                else:
                                    animation.stop()
                                    print(f"\n  {RED}Still not reachable — check logs above.{RESET}\n")
                                    sys.exit(1)
                                break  # exit the outer tick loop
                            else:
                                print(f"\n  {DIM}Aborted.{RESET}\n")
                                sys.exit(0)
                        # ── Generic crash ─────────────────────────────────────
                        else:
                            print(f"\n  {YELLOW}Fix the error above, then run  {BOLD}python server.py{RESET}  again.\n")
                            sys.exit(1)
            time.sleep(2)
        else:
            # Loop exhausted without a break — server never became reachable
            animation.stop()
            print(f"\n\n  {YELLOW}Server did not respond after 300 s.{RESET}")
            print(f"  Checking container logs …\n")
            run(f"{COMPOSE} logs --tail=50 server", check=False)
            print(f"\n  {DIM}If the server is still starting, run  {BOLD}python server.py{RESET}{DIM}  again.{RESET}\n")
            sys.exit(1)

        # -- 5. Immediate backup on start + launch scheduler -----------------------
        startup_backup_time = None
        if backup_enabled:
            animation.update("creating startup backup")
            startup_backup_time = run_backup(silent=True)
            start_scheduler(interval_hours=BACKUP_INTERVAL)
        rows = build_dashboard_rows(ip, backup_enabled, startup_backup_time=startup_backup_time)
        animation.stop()
        _, _, access_value = access_display(ip)
        if not interactive:
            print(f"\n  {GREEN}[OK]{RESET}  Fortispass is running in the background.")
            print(f"  {DIM}Access:{RESET} {access_value}")
            print(f"  {DIM}Run  python server.py  in a terminal to open the live dashboard.{RESET}\n")
            return

        render_dashboard(rows, ip)
        set_terminal_title(f"fortispass ({access_value})")

        # -- 6. Live dashboard (60s refresh) --------------------------------------
        result = attach_to_dashboard(ip, backup_enabled, show_opening_animation=False)
        if result == "detached":
            print(f"\n  {DIM}Detached. Fortispass is still running at {access_value}.{RESET}")
            print(f"  {DIM}Run  python server.py  to reopen the live dashboard.{RESET}\n")
            handoff_to_interactive_shell(access_value)
        return
    except KeyboardInterrupt:
        animation.stop()
        restore_terminal_state()
        return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
