"""
restore.py — fortispass server restore from Google Drive backup.

Downloads the latest (or a chosen) backup from Drive, decrypts it with
your 32-word passphrase, restores the PostgreSQL database and .env, then
restarts the Docker stack.

Usage:
  python restore.py           # restore latest backup
  python restore.py --list    # list available backups and pick one
"""

import io
import os
import platform
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

# Ensure tools/ is on the path so `from backup import ...` works regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))

# -- ANSI ----------------------------------------------------------------------
if platform.system() == "Windows":
    os.system("color")
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"

HERE    = Path(__file__).parent.parent.resolve()  # project root, not tools/
COMPOSE = "docker compose -f docker-compose.yml -f docker-compose.local.yml"

BLUE   = "[38;2;58;111;216m"   # #3A6FD8
WHITE  = "[38;2;255;255;255m"  # #FFFFFF
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



def clr():
    os.system("cls" if platform.system() == "Windows" else "clear")


def run(cmd, check=True):
    return subprocess.run(cmd, shell=True, cwd=str(HERE), check=check)


def run_out(cmd):
    r = subprocess.run(cmd, shell=True, cwd=str(HERE),
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def check_deps():
    missing = []
    for pkg in ["cryptography", "google.oauth2", "googleapiclient"]:
        try:
            __import__(pkg.replace(".", "/").split("/")[0])
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"  {RED}Missing packages:{RESET} {', '.join(missing)}")
        print("  Run: pip install cryptography google-auth google-auth-httplib2 google-api-python-client")
        sys.exit(1)


def format_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    elif n < 1024 ** 2:
        return f"{n/1024:.1f}KB"
    else:
        return f"{n/1024**2:.1f}MB"


def format_ts(ts_str: str) -> str:
    try:
        t = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return t.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ts_str


def main():
    clr()
    print(ASCII_ART + "\n")
    print(f"  {BOLD}fortispass — Restore from Backup{RESET}\n")
    print(f"  {DIM}{'-' * 46}{RESET}\n")

    check_deps()

    # Import after dep check
    from backup import (
        load_config, _drive_service, get_or_create_folder,
        list_backups, download_backup, decrypt_backup,
        passphrase_to_key, DRIVE_FOLDER, LOCAL_CREDS
    )

    # -- Resolve credentials ---------------------------------------------------
    # Works in two modes:
    #   1. Config exists on this machine (backup was set up here) — use stored creds.
    #   2. Fresh machine / disaster recovery — ask for the credentials JSON path.
    cfg        = load_config()
    creds_path = None  # None = _drive_service() uses LOCAL_CREDS automatically

    if cfg and cfg.get("enabled") and LOCAL_CREDS.exists():
        # Happy path — configured locally already
        pass
    else:
        if cfg and cfg.get("enabled") and not LOCAL_CREDS.exists():
            print(f"  {YELLOW}Credentials file not found locally.{RESET}")
        else:
            print(f"  {DIM}No local backup config found — running in recovery mode.{RESET}")
        print()
        while True:
            raw = input(
                "  Path to your Google service-account credentials JSON\n"
                "  (the same file used when backups were first set up): "
            ).strip().strip("\'\"")
            p = Path(os.path.expanduser(raw))
            if p.exists():
                creds_path = str(p)
                break
            print(f"  {RED}File not found: {p}{RESET}  — try again.\n")
        print()

    # -- Connect to Drive ------------------------------------------------------
    print("  Connecting to Google Drive …", end=" ", flush=True)
    try:
        svc = _drive_service(creds_path)
        print(f"{GREEN}done{RESET}\n")
    except Exception as e:
        print(f"\n  {RED}Could not connect to Drive:{RESET} {e}")
        sys.exit(1)

    # -- Find backup folder ----------------------------------------------------
    # Use stored folder_id if available (most reliable).
    # Otherwise search by name — never create a new folder during restore.
    folder_id = (cfg or {}).get("folder_id")
    if not folder_id:
        print(f"  Searching for Drive folder '{DRIVE_FOLDER}' …", end=" ", flush=True)
        try:
            q = (f"name='{DRIVE_FOLDER}' and "
                 f"mimeType='application/vnd.google-apps.folder' and trashed=false")
            resp    = svc.files().list(q=q, fields="files(id,name)").execute()
            folders = resp.get("files", [])
            if not folders:
                print(f"\n\n  {RED}Folder '{DRIVE_FOLDER}' not found on Google Drive.{RESET}")
                print(f"  Make sure you are using the same service-account credentials")
                print(f"  that were used when backups were set up.\n")
                sys.exit(1)
            if len(folders) > 1:
                print(f"{YELLOW}found {len(folders)} folders with that name — using the first{RESET}")
            else:
                print(f"{GREEN}found{RESET}")
            folder_id = folders[0]["id"]
        except Exception as e:
            print(f"\n  {RED}Drive search failed:{RESET} {e}")
            sys.exit(1)

    # -- List backups ----------------------------------------------------------
    print("  Listing backups …", end=" ", flush=True)
    try:
        backups = list_backups(svc, folder_id)
        print(f"{GREEN}{len(backups)} found{RESET}\n")
    except Exception as e:
        print(f"\n  {RED}Could not list backups:{RESET} {e}")
        sys.exit(1)

    if not backups:
        print(f"  {YELLOW}No backups found in Drive folder '{DRIVE_FOLDER}'.{RESET}")
        print(f"  {DIM}folder_id used: {folder_id}{RESET}")
        sys.exit(1)

    # -- Pick backup -----------------------------------------------------------
    pick_list = "--list" in sys.argv

    if pick_list or len(backups) > 1:
        print(f"  {BOLD}Available backups ({len(backups)} total):{RESET}\n")
        display = backups[:20]  # cap list at 20
        for i, b in enumerate(display):
            size = format_size(int(b.get("size", 0)))
            ts   = format_ts(b.get("createdTime", ""))
            tag  = f"  {GREEN}<- latest{RESET}" if i == 0 else ""
            print(f"  {BOLD}{i+1:>2}.{RESET}  {ts}  {DIM}{size}{RESET}{tag}")
        print()

        if pick_list:
            while True:
                raw = input(f"  Choose backup [1–{len(display)}, default=1]: ").strip()
                if raw == "":
                    chosen = 0
                    break
                try:
                    chosen = int(raw) - 1
                    if 0 <= chosen < len(display):
                        break
                except ValueError:
                    pass
                print(f"  {RED}Invalid choice.{RESET}")
        else:
            chosen = 0  # auto-pick latest
    else:
        chosen = 0

    selected = backups[chosen]
    print(f"  Restoring: {BOLD}{selected['name']}{RESET}  ({format_ts(selected.get('createdTime',''))})\n")

    # -- Confirm ---------------------------------------------------------------
    print(f"  {YELLOW}{BOLD}WARNING:{RESET} This will overwrite your current database and .env.")
    answer = input(f"  Type  {BOLD}yes{RESET}  to continue: ").strip().lower()
    if answer != "yes":
        print(f"\n  {DIM}Aborted.{RESET}\n")
        sys.exit(0)

    # -- Passphrase ------------------------------------------------------------
    print()
    while True:
        raw = input("  Enter your 32-word restore passphrase: ").strip()
        words = [w.lower() for w in raw.split()]
        if len(words) == 32:
            break
        print(f"  {RED}Expected 32 words, got {len(words)}. Try again.{RESET}\n")

    # -- Download --------------------------------------------------------------
    print("\n  Downloading backup …", end=" ", flush=True)
    try:
        blob = download_backup(svc, selected["id"])
        print(f"{GREEN}done{RESET}  ({format_size(len(blob))})")
    except Exception as e:
        print(f"\n  {RED}Download failed:{RESET} {e}")
        sys.exit(1)

    # -- Decrypt ---------------------------------------------------------------
    print("  Decrypting …", end=" ", flush=True)
    try:
        key     = passphrase_to_key(words)
        archive = decrypt_backup(blob, key)
        print(f"{GREEN}done{RESET}")
    except ValueError as e:
        print(f"\n  {RED}{e}{RESET}")
        sys.exit(1)

    # -- Unpack archive --------------------------------------------------------
    print("  Unpacking …", end=" ", flush=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            sql_data = None
            env_data = None
            for member in tar.getmembers():
                f = tar.extractfile(member)
                if f is None:
                    continue
                data = f.read()
                if member.name == "fortispass_db.sql":
                    sql_data = data
                elif member.name == ".env":
                    env_data = data
        print(f"{GREEN}done{RESET}")
    except Exception as e:
        print(f"\n  {RED}Failed to unpack archive:{RESET} {e}")
        sys.exit(1)

    # -- Restore .env ----------------------------------------------------------
    if env_data:
        print("  Restoring .env …", end=" ", flush=True)
        env_path = HERE / ".env"
        if env_path.exists():
            env_path.replace(HERE / ".env.pre_restore")
        env_path.write_bytes(env_data)
        print(f"{GREEN}done{RESET}")
    else:
        print(f"  {YELLOW}No .env found in backup — keeping existing .env{RESET}")

    # -- Stop running stack (prevents active-connection errors on DROP DATABASE) -
    print("  Stopping running containers …", end=" ", flush=True)
    try:
        run(f"{COMPOSE} down", check=False)  # check=False — ok if already stopped
        print(f"{GREEN}done{RESET}")
    except Exception:
        print(f"{GREEN}ok{RESET}")  # already stopped

    # -- Start postgres only (needed for restore) ------------------------------
    print("  Starting database container …", end=" ", flush=True)
    try:
        run(f"{COMPOSE} up -d postgres", check=True)
        # Wait for postgres to be ready — sleep first so we don't hit it cold
        import time
        time.sleep(2)
        for _ in range(20):
            result = subprocess.run(
                f"{COMPOSE} exec -T postgres pg_isready -U fortispass",
                shell=True, cwd=str(HERE), capture_output=True
            )
            if result.returncode == 0:
                break
            time.sleep(2)
        print(f"{GREEN}done{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"\n  {RED}Failed to start postgres:{RESET} {e}")
        sys.exit(1)

    # -- Restore database ------------------------------------------------------
    if sql_data:
        print("  Restoring database …", end=" ", flush=True)
        try:
            # Load .env to get postgres password
            env_vars = {}
            env_file = HERE / ".env"
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        env_vars[k.strip()] = v.strip()

            pg_pass = env_vars.get("POSTGRES_PASSWORD", "")
            env_copy = os.environ.copy()
            env_copy["PGPASSWORD"] = pg_pass

            # Drop + recreate schema, then restore
            drop_cmd = (
                f"{COMPOSE} exec -T postgres psql -U fortispass -d postgres "
                f"-c 'DROP DATABASE IF EXISTS fortispass; CREATE DATABASE fortispass;'"
            )
            subprocess.run(drop_cmd, shell=True, cwd=str(HERE),
                           env=env_copy, check=True, capture_output=True)

            restore_cmd = f"{COMPOSE} exec -T postgres psql -U fortispass -d fortispass"
            result = subprocess.run(
                restore_cmd, shell=True, cwd=str(HERE),
                input=sql_data, env=env_copy,
                capture_output=True
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode(errors='replace'))
            print(f"{GREEN}done{RESET}")
        except Exception as e:
            print(f"\n  {RED}Database restore failed:{RESET} {e}")
            sys.exit(1)
    else:
        print(f"  {YELLOW}No database dump in backup — skipping database restore{RESET}")

    # -- Full stack restart ----------------------------------------------------
    print("  Starting full stack …", end=" ", flush=True)
    try:
        run(f"{COMPOSE} up --build -d", check=True)
        print(f"{GREEN}done{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"\n  {RED}Stack start failed:{RESET} {e}")
        sys.exit(1)

    print(f"\n  {GREEN}{BOLD}[OK]  Restore complete.{RESET}")
    print(f"  Your server is back up at  {WHITE}http://localhost:8080{RESET}")
    print(f"  Run  {BOLD}python server.py{RESET}  to view the dashboard.\n")


if __name__ == "__main__":
    main()
