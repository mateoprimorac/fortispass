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
import secrets
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

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
    print(f"  {BOLD}  1.{RESET}  {GREEN}start{RESET}               python server.py")
    print(f"  {BOLD}  2.{RESET}  {GREEN}start --interval X{RESET}  python server.py --interval X  {DIM}(1–48h, default 4){RESET}")
    print(f"  {BOLD}  3.{RESET}  {GREEN}start --port X{RESET}      python server.py --port X      {DIM}(default 8080){RESET}")
    print(f"  {BOLD}  4.{RESET}  {GREEN}start --max-devices X{RESET} python server.py --max-devices X  {DIM}(default 3){RESET}")
    print(f"  {BOLD}  5.{RESET}  {YELLOW}--restore{RESET}           restore the server from a Google Drive backup")
    print(f"  {BOLD}  6.{RESET}  {YELLOW}--backup{RESET}            configure or run a Google Drive backup")
    print(f"  {BOLD}  7.{RESET}  {YELLOW}--stop{RESET}              stop the server (data volumes preserved)")
    print(f"  {BOLD}  8.{RESET}  {RED}--wipe{RESET}              stop the server and permanently delete all data")
    print(f"\n  {DIM}{'─' * 46}{RESET}\n")
    choice = input(f"  Enter a number to run it, or press {BOLD}Enter{RESET} to start normally: ").strip()
    print()
    if choice == "1" or choice == "":
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
        print(f"  {DIM}Unrecognised — starting normally.{RESET}\n")
        return "start"

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
    print(f"  {BOLD}Stopping fortispass server …{RESET}\n")
    print(f"  {RED}{BOLD}{'=' * 54}{RESET}")
    print(f"  {RED}{BOLD}  DESTRUCTIVE OPERATION — READ CAREFULLY             {RESET}")
    print(f"  {RED}{BOLD}{'=' * 54}{RESET}\n")
    print(f"  {YELLOW}This will permanently delete:{RESET}")
    print(f"  {YELLOW}  •  The PostgreSQL database (all user vaults){RESET}")
    print(f"  {YELLOW}  •  The Redis store (all active sessions){RESET}")
    print(f"  {YELLOW}  •  All Docker volumes for this stack{RESET}\n")
    print(f"  {RED}This CANNOT be undone. There is no recovery unless you{RESET}")
    print(f"  {RED}have a Google Drive backup configured.{RESET}\n")
    print(f"  {DIM}Only proceed if you are intentionally wiping this server{RESET}")
    print(f"  {DIM}and know exactly what you are doing.{RESET}\n")
    _ans = input(f"  Type  {BOLD}CONFIRM{RESET}  to wipe everything, or anything else to abort: ").strip()
    if _ans != "CONFIRM":
        print(f"\n  {DIM}Aborted — nothing was changed.{RESET}\n")
        _sys.exit(0)
    print()
    try:
        subprocess.run(f"{COMPOSE} down -v", shell=True, cwd=str(HERE), check=True)
        print(f"\n  {GREEN}[OK]{RESET}  All containers and data volumes removed.")
        print(f"      Run  {BOLD}python server.py{RESET}  to start fresh.\n")
    except subprocess.CalledProcessError:
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
    clr = lambda: os.system("cls" if platform.system() == "Windows" else "clear")
    clr()
    print(ASCII_ART + "\n")
    print(f"  {BOLD}Stopping fortispass server …{RESET}\n")
    try:
        subprocess.run(f"{COMPOSE} down", shell=True, cwd=str(HERE), check=True)
        print(f"\n  {GREEN}[OK]{RESET}  Server stopped. Data volumes are intact.")
        print(f"      Run  {BOLD}python server.py{RESET}  to start again.\n")
    except subprocess.CalledProcessError:
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
    os.system("cls" if platform.system() == "Windows" else "clear")


def run(cmd, check=True):
    return subprocess.run(cmd, shell=True, cwd=str(HERE), check=check)


def run_out(cmd):
    r = subprocess.run(cmd, shell=True, cwd=str(HERE),
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


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


def server_reachable(host: str = "localhost"):
    """Try localhost first (always works for local Docker), then the LAN IP."""
    import urllib.request
    for h in (["localhost", host] if host != "localhost" else ["localhost"]):
        try:
            urllib.request.urlopen(f"http://{h}:{_port}/health", timeout=3)
            return True
        except Exception:
            continue
    return False


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
    jwt_secret      = b64(secrets.token_bytes(32))
    server_hmac_key = b64(secrets.token_bytes(32))
    postgres_pw     = secrets.token_urlsafe(24)
    redis_pw        = secrets.token_urlsafe(24)
    signing_key     = nacl.signing.SigningKey.generate()
    sign_key_seed   = b64(bytes(signing_key))

    contents = (
        "# fortispass — local environment\n"
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
        f"RELAY_URL=http://{ip}:{_port}\n"
        f"MAX_DEVICES_PER_VAULT={_max_devices}\n"
    )
    (HERE / ".env").write_text(contents)


def patch_relay_url(ip: str) -> None:
    """Keep RELAY_URL and LISTEN_PORT in an existing .env in sync.
    Called every startup so a --port flag or IP change takes effect without
    regenerating secrets. Docker Compose reads LISTEN_PORT from .env to set
    the host-side port mapping — if it's stale the health check polls the
    wrong port and the server appears unreachable."""
    import re
    text = ENV_PATH.read_text()
    changed = False

    # Update RELAY_URL to current IP + port
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
        parts = [f"RELAY_URL → http://{ip}:{_port}", f"LISTEN_PORT={_port}"]
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


def draw_dashboard(ip, backup_enabled, startup_backup_time=None):
    clr()
    print(ASCII_ART + "\n")
    print(f"  {DIM}{'-' * 46}{RESET}")

    healthy = server_reachable(ip)
    uptime  = get_uptime() if healthy else "—"

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
    rows.append(("IP:Port", f"{WHITE}{ip}:{_port}{RESET}"))

    for label, value in rows:
        print(f"  {BOLD}{label:<14}{RESET}  {value}")

    print(f"\n  {DIM}{'-' * 46}{RESET}")
    print(f"  {DIM}If connecting from another device, make sure{RESET}")
    print(f"  {DIM}port {_port} is allowed in your firewall.{RESET}")
    print(f"  {DIM}Ctrl+C to detach, server keeps running{RESET}")
    print(f"  {DIM}python server.py --stop  ·  python server.py --restore{RESET}\n")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    clr()
    print(ASCII_ART + "\n")

    # -- 0. Docker check -------------------------------------------------------
    # Verify Docker is installed and the daemon is running before doing anything.
    probe = subprocess.run(
        "docker info", shell=True, cwd=str(HERE),
        capture_output=True, text=True,
    )
    if probe.returncode != 0:
        print(f"  {RED}{'=' * 54}{RESET}")
        print(f"  {RED}{BOLD}  Docker is not running or not installed.{RESET}")
        print(f"  {RED}{'=' * 54}{RESET}\n")
        print(f"  fortispass runs inside Docker. To fix this:\n")
        print(f"  {BOLD}Windows / macOS:{RESET}")
        print(f"    1. Download Docker Desktop from  https://docker.com/products/docker-desktop")
        print(f"    2. Install and launch it")
        print(f"    3. Wait for the whale icon to appear in the system tray")
        print(f"    4. Run  python server.py  again\n")
        print(f"  {BOLD}Linux:{RESET}")
        print(f"    1. Install Docker Engine:  https://docs.docker.com/engine/install/")
        print(f"    2. Start the service:      sudo systemctl start docker")
        print(f"    3. (Optional) add yourself to the docker group so you do not need sudo:")
        print(f"       sudo usermod -aG docker $USER   then log out and back in")
        print(f"    4. Run  python server.py  again\n")
        input(f"  Press Enter to exit … ")
        sys.exit(1)

    # Resolve IP early — needed for RELAY_URL which is baked into .env and
    # handed to the extension inside every QR payload and session create response.
    # localhost doesn't reach Docker on all machines, so we always use the LAN IP.
    ip = local_ip()

    # -- 1. .env ---------------------------------------------------------------
    if ENV_PATH.exists():
        print(f"  {GREEN}[OK]{RESET}  .env found — skipping secret generation\n")
        patch_relay_url(ip)   # keep RELAY_URL in sync with current LAN IP
    else:
        print(f"  Generating secrets …", end=" ", flush=True)
        generate_env(ip)
        print(f"{GREEN}done{RESET}\n")

    # -- 2. Backup setup (asked once, stored in .backup_config.json) -----------
    backup_enabled = False

    try:
        from backup import is_configured, load_config, setup_wizard, run_backup, start_scheduler

        if not is_configured():
            print(f"  {DIM}{'-' * 46}{RESET}\n")
            setup_wizard(interval_hours=BACKUP_INTERVAL or 4)
            print(f"  {DIM}{'-' * 46}{RESET}\n")

        cfg = load_config()
        if cfg and cfg.get("enabled"):
            backup_enabled = True

    except ImportError:
        print(f"  {DIM}backup.py not found — Drive backups unavailable.{RESET}\n")

    # -- 3. Build + start Docker -----------------------------------------------
    print(f"  {BOLD}Building and starting Docker stack …{RESET}\n")
    try:
        run(f"{COMPOSE} up --build -d")
    except subprocess.CalledProcessError:
        print(f"\n  {RED}{'=' * 54}{RESET}")
        print(f"  {RED}{BOLD}  Docker is not running or not installed.{RESET}")
        print(f"  {RED}{'=' * 54}{RESET}\n")
        print(f"  fortispass runs inside Docker. To fix this:\n")
        print(f"  {BOLD}Windows / macOS:{RESET}")
        print(f"    1. Download Docker Desktop from  https://docker.com/products/docker-desktop")
        print(f"    2. Install and launch it")
        print(f"    3. Wait for the whale icon to appear in the system tray")
        print(f"    4. Run  python server.py  again\n")
        print(f"  {BOLD}Linux:{RESET}")
        print(f"    1. Install Docker Engine:  https://docs.docker.com/engine/install/")
        print(f"    2. Start the service:      sudo systemctl start docker")
        print(f"    3. (Optional) add yourself to the docker group so you do not need sudo:")
        print(f"       sudo usermod -aG docker $USER   then log out and back in")
        print(f"    4. Run  python server.py  again\n")
        input(f"  Press Enter to exit … ")
        sys.exit(1)

    # -- 4. Wait for /health ---------------------------------------------------
    print(f"\n  Waiting for server …", end="", flush=True)
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
                        print()
                        ans = input(f"  Type  {BOLD}CONFIRM{RESET}  to wipe and restart, or Enter to abort: ").strip()
                        if ans == "CONFIRM":
                            print(f"\n  Wiping volumes …", end=" ", flush=True)
                            run(f"{COMPOSE} down -v", check=False)
                            print(f"{GREEN}done{RESET}")
                            ENV_PATH.unlink(missing_ok=True)
                            print(f"  Regenerating secrets …", end=" ", flush=True)
                            generate_env(ip)
                            print(f"{GREEN}done{RESET}\n")
                            print(f"  Restarting …\n")
                            run(f"{COMPOSE} up --build -d")
                            print(f"\n  Waiting for server …", end="", flush=True)
                            for _ in range(90):
                                if server_reachable(ip):
                                    print(f"  {GREEN}[OK]{RESET}  Server is up.\n")
                                    break
                                print(".", end="", flush=True)
                                time.sleep(2)
                            else:
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

            # Every 30s print a live status line so the user can see what's still starting
            if tick % 15 == 0:
                statuses = []
                for line in state.splitlines():
                    parts = line.strip().split()
                    if parts:
                        statuses.append(f"{parts[0]}:{parts[-1]}" if len(parts) > 1 else parts[0])
                if statuses:
                    print(f"\n  {DIM}[{tick*2}s] {' · '.join(statuses)}{RESET}", end="", flush=True)

        print(".", end="", flush=True)
        time.sleep(2)
    else:
        # Loop exhausted without a break — server never became reachable
        print(f"\n\n  {YELLOW}Server did not respond after 300 s.{RESET}")
        print(f"  Checking container logs …\n")
        run(f"{COMPOSE} logs --tail=50 server", check=False)
        print(f"\n  {DIM}If the server is still starting, run  {BOLD}python server.py{RESET}{DIM}  again.{RESET}\n")
        sys.exit(1)
    print()

    # -- 5. Immediate backup on start + launch scheduler -----------------------
    startup_backup_time = None
    if backup_enabled:
        print(f"\n  Running startup backup …")
        startup_backup_time = run_backup(silent=False)
        if startup_backup_time:
            print(f"  {GREEN}[OK]{RESET}  Backup complete.")
        start_scheduler(interval_hours=BACKUP_INTERVAL)
        _ival = BACKUP_INTERVAL or load_config().get('interval_hours', 4)
        print(f"  {DIM}Next automatic backup in {_ival}h.{RESET}\n")

    # -- 6. Live dashboard (60s refresh) --------------------------------------
    try:
        while True:
            draw_dashboard(ip, backup_enabled, startup_backup_time=startup_backup_time)
            time.sleep(60)
    except KeyboardInterrupt:
        print(f"\n  {DIM}Detached. Server is still running in the background.{RESET}")
        print(f"  Run  {BOLD}python server.py --stop{RESET}  to shut it down.\n")


if __name__ == "__main__":
    main()
