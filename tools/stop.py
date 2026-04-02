"""
stop.py — fortispass server teardown.

Stops and removes all containers. Volumes (database, Redis) are kept by
default so your data survives. Pass --wipe to delete everything.

Usage:
  python stop.py           # stop containers, keep data volumes
  python stop.py --wipe    # stop containers AND delete all data
"""

import os
import platform
import subprocess
import sys

sys.dont_write_bytecode = True

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

HERE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
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



def run(cmd, check=True):
    return subprocess.run(cmd, shell=True, cwd=HERE, check=check)


def secure_delete_file(path: str):
    """Best-effort overwrite-then-delete for small local secret files."""
    if not os.path.isfile(path):
        return
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    size = os.path.getsize(path)
    if size > 0:
        chunk_size = 64 * 1024
        with open(path, "r+b", buffering=0) as f:
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
    os.remove(path)


def clr():
    os.system("cls" if platform.system() == "Windows" else "clear")


def main():
    wipe = "--wipe" in sys.argv

    clr()
    print(ASCII_ART + "\n")
    if not wipe:
        print(f"  {BOLD}Stopping fortispass server …{RESET}\n")

    if wipe:
        print(f"  {RED}{BOLD}{'=' * 54}{RESET}")
        print(f"  {RED}{BOLD}  DESTRUCTIVE OPERATION — READ CAREFULLY             {RESET}")
        print(f"  {RED}{BOLD}{'=' * 54}{RESET}\n")
        print(f"  {YELLOW}This will permanently delete:{RESET}")
        print(f"  {YELLOW}  •  The PostgreSQL database (all user vaults){RESET}")
        print(f"  {YELLOW}  •  The Redis store (all active sessions){RESET}")
        print(f"  {YELLOW}  •  All Docker volumes for this stack{RESET}\n")
        print(f"  {RED}This CANNOT be undone. There is no recovery unless you{RESET}")
        print(f"  {RED}have a Google Drive backup configured.{RESET}\n")
        for remaining in range(10, 0, -1):
            print(f"  {DIM}Confirmation unlocks in {remaining}s …{RESET}", end="\r", flush=True)
            import time
            time.sleep(1)
        print(" " * 60, end="\r")
        answer = input(f"  Type  {BOLD}CONFIRM{RESET}  to wipe everything, or anything else to abort: ").strip()
        if answer != "CONFIRM":
            print(f"\n  {DIM}Aborted — nothing was changed.{RESET}\n")
            sys.exit(0)
        print()

    try:
        if wipe:
            print(f"  Removing containers and volumes …", end=" ", flush=True)
            run(f"{COMPOSE} down -v")
            secure_delete_file(os.path.join(HERE, ".env"))
            secure_delete_file(os.path.join(HERE, ".backup_config.json"))
        else:
            print(f"  Stopping containers (data volumes preserved) …", end=" ", flush=True)
            run(f"{COMPOSE} down")
        print(f"{GREEN}done{RESET}\n")
    except subprocess.CalledProcessError:
        print(f"\n  {RED}Docker command failed.{RESET}")
        print("  Make sure Docker Desktop is running and try again.")
        sys.exit(1)

    if wipe:
        print(f"  {GREEN}[OK]{RESET}  All containers and data volumes removed.")
        print(f"      Run  {BOLD}python server.py{RESET}  to start fresh.\n")
    else:
        print(f"  {GREEN}[OK]{RESET}  Server stopped. Data volumes are intact.")
        print(f"      Run  {BOLD}python server.py{RESET}  to start again.")
        print(f"      Run  {BOLD}python tools/stop.py --wipe{RESET}  to also delete all data.\n")


if __name__ == "__main__":
    main()
