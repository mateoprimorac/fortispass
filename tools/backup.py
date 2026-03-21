"""
backup.py — fortispass backup engine.

How encryption works:
  - At setup, a random 32-byte AES key is generated and stored in
    .backup_config.json. This is used to encrypt every backup automatically.
  - A 32-word passphrase is derived FROM that same key (displayed once at
    setup, never stored). It is the ONLY way to decrypt a backup during
    restore. Keep it safe.

  Encryption format (BKY1 file):
    [4 bytes magic "BKY1"] [12 bytes AES nonce]
    [remaining: AES-256-GCM ciphertext of tar.gz(pg_dump + .env)]

  The restore key is stored as base64 in .backup_config.json.
  The passphrase is simply: base64(key) split into groups mapped to words.
  On restore, the user types the passphrase -> words -> key -> decrypt.

Credentials file:
  Copied into .fortispass_credentials.json at setup time so the original
  path doesn't matter anymore.

External dependencies (pip install):
  cryptography
  google-auth
  google-auth-httplib2
  google-api-python-client
"""

import base64
import io
import json
import os
import platform
import random
import shutil
import secrets
import subprocess
import sys
import tarfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# -- ANSI ----------------------------------------------------------------------
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"

HERE         = Path(__file__).parent.parent.resolve()  # project root, not tools/
ENV_PATH     = HERE / ".env"
BACKUP_CFG   = HERE / ".backup_config.json"
LOCAL_CREDS  = HERE / ".fortispass_credentials.json"   # copy stored here
COMPOSE      = "docker compose -f docker-compose.yml -f docker-compose.local.yml"
MAGIC        = b"BKY1"
MAX_BACKUPS  = 48
DRIVE_FOLDER = "fortispass-backups"

# -- Wordlist for passphrase display (256 words, one per 8-bit chunk of key) ---
# The 32-byte key = 256 bits. We encode it as 32 words (one per byte, 0-255).
# We use a 256-word list so every byte maps to exactly one word.
WORDLIST_256 = [
    "abbey","acorn","actor","agent","agile","alarm","album","alert","algae","alien",
    "alley","alloy","alone","altar","amber","ample","angel","angle","anvil","apple",
    "apron","arbor","arena","armor","aroma","arrow","atlas","attic","audio","avid",
    "award","baked","baker","banjo","barge","baron","basic","basil","basin","batch",
    "bayou","beard","beast","beech","bevel","bison","blast","blend","bless","bliss",
    "bloom","blunt","bogus","boost","bound","braid","brave","brawn","bread","brick",
    "brine","brisk","brood","brook","broth","brown","budge","bulge","bumpy","bunch",
    "burnt","burst","buyer","camel","candy","cargo","cedar","chain","chalk","chant",
    "charm","chase","chest","chief","child","chord","civic","clamp","clean","clear",
    "click","cliff","cloak","clock","cloud","clown","coral","craft","crane","crisp",
    "cross","crown","cubic","curly","cycle","daily","dairy","daisy","delta","depot",
    "digit","disco","diver","dodge","dolly","doubt","draft","drain","drawl","dream",
    "dried","drift","drill","drink","drove","drums","eager","eagle","early","ebony",
    "elbow","elder","elite","ember","empty","enjoy","entry","envoy","epoch","erode",
    "essay","evade","event","exact","exert","exile","extra","fable","facet","fairy",
    "fancy","fatal","feast","ferry","fetch","fiber","finch","first","fjord","flare",
    "flash","flask","fleet","flesh","flint","flock","flood","floss","flour","fluid",
    "flush","focal","force","forge","found","frail","frame","frank","fresh","froze",
    "fungi","gauze","gecko","ghost","giant","given","gleam","glide","globe","gloom",
    "glory","gloss","glove","gnash","gorge","grace","grade","grain","grand","grasp",
    "graze","greed","greet","grief","grill","grind","groan","gross","grove","growl",
    "guava","guild","gusto","hardy","harsh","hazel","heavy","hedge","helix","heron",
    "hitch","hoard","holly","honey","honor","hound","humid","ideal","igloo","image",
    "ionic","ivory","jelly","jewel","jolly","joust","judge","juicy","karma","kayak",
    "knack","koala","kudos","later","lemon","level","lilac","lodge","lofty","lunar",
    "maxim","merit","metal","mimic","mural","zebra",
]

assert len(WORDLIST_256) == 256, f"Wordlist must have exactly 256 words, has {len(WORDLIST_256)}"


# -----------------------------------------------------------------------------
# Key <-> Passphrase conversion
# -----------------------------------------------------------------------------

def key_to_passphrase(key: bytes) -> list[str]:
    """Convert 32-byte key to 32 words (one word per byte)."""
    assert len(key) == 32
    return [WORDLIST_256[b] for b in key]


def passphrase_to_key(words: list[str]) -> bytes:
    """Convert 32-word passphrase back to 32-byte key. Raises ValueError on bad words."""
    if len(words) != 32:
        raise ValueError(f"Expected 32 words, got {len(words)}")
    lookup = {w: i for i, w in enumerate(WORDLIST_256)}
    result = bytearray()
    for i, w in enumerate(words):
        w = w.lower().strip()  # tolerate capitalisation and stray whitespace
        if w not in lookup:
            raise ValueError(f"Unknown word at position {i+1}: '{w}'")
        result.append(lookup[w])
    return bytes(result)


def format_phrase(words: list[str]) -> str:
    """Pretty-print 32 words in 4 rows of 8, numbered."""
    lines = []
    for row in range(4):
        parts = []
        for col in range(8):
            i = row * 8 + col
            parts.append(f"{i+1:>2}. {words[i]:<10}")
        lines.append("  " + "".join(parts))
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Encryption (uses stored key directly — no KDF needed, key is already random)
# -----------------------------------------------------------------------------

def encrypt_backup(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt plaintext -> BKY1 binary blob using stored backup key."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = secrets.token_bytes(12)
    ct    = AESGCM(key).encrypt(nonce, plaintext, None)
    return MAGIC + nonce + ct


def decrypt_backup(blob: bytes, key: bytes) -> bytes:
    """Decrypt BKY1 blob -> original plaintext. Raises on wrong key or corruption."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if blob[:4] != MAGIC:
        raise ValueError("Not a valid fortispass backup file (bad magic bytes)")
    nonce = blob[4:16]
    ct    = blob[16:]
    try:
        return AESGCM(key).decrypt(nonce, ct, None)
    except Exception:
        raise ValueError("Decryption failed — wrong passphrase or corrupted backup")


# -----------------------------------------------------------------------------
# Database dump + archive
# -----------------------------------------------------------------------------

def load_env() -> dict:
    result = {}
    if not ENV_PATH.exists():
        return result
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


def pg_dump() -> bytes:
    env     = load_env()
    pg_pass = env.get("POSTGRES_PASSWORD", "")
    cmd     = f"{COMPOSE} exec -T postgres pg_dump -U fortispass -d fortispass --no-password"
    env_copy = os.environ.copy()
    env_copy["PGPASSWORD"] = pg_pass
    result = subprocess.run(cmd, shell=True, cwd=str(HERE),
                            capture_output=True, env=env_copy)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode(errors='replace')}")
    return result.stdout


def build_archive() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        dump = pg_dump()
        info = tarfile.TarInfo(name="fortispass_db.sql")
        info.size = len(dump)
        tar.addfile(info, io.BytesIO(dump))
        if ENV_PATH.exists():
            env_bytes = ENV_PATH.read_bytes()
            info2 = tarfile.TarInfo(name=".env")
            info2.size = len(env_bytes)
            tar.addfile(info2, io.BytesIO(env_bytes))
    return buf.getvalue()


# -----------------------------------------------------------------------------
# Google Drive
# -----------------------------------------------------------------------------

def _drive_service(creds_path: str = None):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print(f"\n  {RED}Missing Google API libraries.{RESET}")
        print(f"  Install them with:\n")
        print(f"  {BOLD}  pip install google-auth google-auth-httplib2 google-api-python-client{RESET}\n")
        raise SystemExit(1)
    path = creds_path or str(LOCAL_CREDS)
    creds = service_account.Credentials.from_service_account_file(
        path, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def get_or_create_folder(service, folder_name: str) -> str:
    q = (f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
         f" and trashed=false")
    resp  = service.files().list(q=q, fields="files(id,name)").execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"]
    meta   = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]


def upload_backup(service, folder_id: str, filename: str, data: bytes) -> str:
    from googleapiclient.http import MediaIoBaseUpload
    meta  = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/octet-stream")
    f     = service.files().create(body=meta, media_body=media, fields="id").execute()
    return f["id"]


def prune_old_backups(service, folder_id: str, keep: int = MAX_BACKUPS) -> int:
    q    = f"'{folder_id}' in parents and trashed=false"
    resp = service.files().list(
        q=q, fields="files(id,name,createdTime)", orderBy="createdTime asc"
    ).execute()
    files     = resp.get("files", [])
    to_delete = files[:max(0, len(files) - keep)]
    for f in to_delete:
        service.files().delete(fileId=f["id"]).execute()
    return len(to_delete)


def list_backups(service, folder_id: str) -> list:
    q    = f"'{folder_id}' in parents and trashed=false"
    resp = service.files().list(
        q=q, fields="files(id,name,createdTime,size)", orderBy="createdTime desc"
    ).execute()
    return resp.get("files", [])


def download_backup(service, file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload
    req  = service.files().get_media(fileId=file_id)
    buf  = io.BytesIO()
    dl   = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

def load_config() -> dict | None:
    if BACKUP_CFG.exists():
        return json.loads(BACKUP_CFG.read_text())
    return None


def save_config(cfg: dict):
    BACKUP_CFG.write_text(json.dumps(cfg, indent=2))


def is_configured() -> bool:
    return load_config() is not None


def get_backup_key() -> bytes | None:
    """Load the stored backup encryption key from config."""
    cfg = load_config()
    if not cfg or not cfg.get("backup_key_b64"):
        return None
    return base64.b64decode(cfg["backup_key_b64"])


# -----------------------------------------------------------------------------
# Passphrase verification wizard
# -----------------------------------------------------------------------------

def verify_passphrase_wizard(words: list[str]) -> bool:
    positions = sorted(random.sample(range(32), 3))
    print(f"\n  {BOLD}Verification{RESET} — type the words at these positions:\n")
    for pos in positions:
        answer = input(f"    Word #{pos+1}: ").strip().lower()
        if answer != words[pos]:
            print(f"\n  {RED}Incorrect.{RESET} Word #{pos+1} should be '{words[pos]}'.")
            return False
    return True


# -----------------------------------------------------------------------------
# Setup wizard
# -----------------------------------------------------------------------------

def _check_google_deps():
    """Exit with a helpful message if Google API libraries are not installed."""
    missing = []
    for pkg in ["google.oauth2", "googleapiclient"]:
        try:
            __import__(pkg.split(".")[0])
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"\n  {RED}Google API libraries are not installed.{RESET}")
        print(f"  Run this command first, then re-run the server:\n")
        print(f"  {BOLD}    pip install google-auth google-auth-httplib2 google-api-python-client{RESET}\n")
        sys.exit(1)


def setup_wizard(interval_hours: int = 4) -> bool:
    """
    First-time interactive setup. Returns True if enabled, False if skipped.
    Saves config and copies credentials file locally on success.
    """
    _check_google_deps()
    print(f"\n  {BOLD}Google Drive Backup Setup{RESET}")
    print(f"  {DIM}{'-' * 44}{RESET}\n")
    print("  fortispass can automatically back up your database and")
    print(f"  server secrets to Google Drive every {interval_hours}h.\n")

    ans = input(f"  Enable Google Drive backups? [{BOLD}y{RESET}/n]: ").strip().lower()
    if ans not in ("y", "yes", ""):
        print(f"\n  {DIM}Skipped. Delete .backup_config.json to be asked again.{RESET}\n")
        save_config({"enabled": False})
        return False

    print()
    print("  You need a Google service account credentials file (JSON key).")
    print("  Guide: https://cloud.google.com/iam/docs/service-accounts-create\n")

    while True:
        raw_path = input("  Path to credentials JSON file: ").strip().strip('"')
        creds_path = Path(os.path.expanduser(raw_path))
        if not creds_path.is_file():
            print(f"  {RED}File not found.{RESET} Try again.\n")
            continue
        try:
            # Copy credentials locally so path changes don't break anything
            shutil.copy2(str(creds_path), str(LOCAL_CREDS))
            # Test the copied file
            svc       = _drive_service()
            folder_id = get_or_create_folder(svc, DRIVE_FOLDER)
            print(f"  {GREEN}[OK]{RESET}  Connected. Credentials saved locally.")
            print(f"       Backups -> Drive folder: {BOLD}{DRIVE_FOLDER}{RESET}\n")
            break
        except Exception as e:
            # Remove failed copy
            if LOCAL_CREDS.exists():
                LOCAL_CREDS.unlink()
            print(f"  {RED}Could not connect:{RESET} {e}\n")
            retry = input("  Try a different file? [y/n]: ").strip().lower()
            if retry not in ("y", "yes"):
                save_config({"enabled": False})
                return False

    # -- Generate backup key and derive passphrase from it ---------------------
    backup_key = secrets.token_bytes(32)
    words      = key_to_passphrase(backup_key)

    while True:
        print(f"  {BOLD}{YELLOW}{'=' * 56}{RESET}")
        print(f"  {BOLD}{YELLOW}  YOUR RESTORE PASSPHRASE — SHOWN ONCE, NEVER AGAIN    {RESET}")
        print(f"  {BOLD}{YELLOW}{'=' * 56}{RESET}\n")
        print(f"  {RED}{BOLD}Write all 32 words down on paper and store them somewhere safe.{RESET}")
        print(f"  {RED}Without them, your backups CANNOT be decrypted.{RESET}\n")
        print(format_phrase(words))
        print()

        input(f"  Press {BOLD}Enter{RESET} when you have written them down …")

        # Clear the terminal so the words are no longer visible before asking
        # the user to type them — prevents trivially reading them off the screen
        os.system("cls" if os.name == "nt" else "clear")

        print(f"  {BOLD}Passphrase hidden.{RESET} Now verify you wrote them down correctly.\n")
        print(f"  {DIM}(The words are gone from the screen on purpose.){RESET}\n")
        if verify_passphrase_wizard(words):
            print(f"\n  {GREEN}[OK]  Passphrase verified.{RESET}")
            break
        else:
            print(f"\n  {YELLOW}Let's try again — here is your passphrase:{RESET}\n")

    # -- Save config (key stored in config, passphrase is never stored) ---------
    cfg = {
        "enabled":        True,
        "folder_id":      folder_id,
        "interval_hours": interval_hours,
        "max_backups":    MAX_BACKUPS,
        "backup_key_b64": base64.b64encode(backup_key).decode(),
        "last_backup":    None,
    }
    save_config(cfg)

    print(f"\n  {GREEN}[OK]  Backup configured.{RESET} Runs every {interval_hours}h automatically.")
    print(f"  {DIM}Your passphrase is only needed during restore — keep it safe.{RESET}\n")
    return True


# -----------------------------------------------------------------------------
# Run a single backup (no passphrase needed — uses stored key)
# -----------------------------------------------------------------------------

def run_backup(silent: bool = False) -> datetime | None:
    """
    Perform one backup using the stored encryption key.
    Returns UTC datetime on success, None on failure.
    """
    cfg = load_config()
    if not cfg or not cfg.get("enabled"):
        return None

    key = get_backup_key()
    if not key:
        if not silent:
            print(f"  {RED}No backup key found in config.{RESET}")
        return None

    try:
        if not silent:
            print("\n  Building backup archive …", end=" ", flush=True)
        archive   = build_archive()
        encrypted = encrypt_backup(archive, key)

        svc = _drive_service()
        ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        fn  = f"fortispass_backup_{ts}.bky"

        if not silent:
            print("uploading …", end=" ", flush=True)
        folder_id = cfg.get("folder_id") or get_or_create_folder(svc, DRIVE_FOLDER)
        upload_backup(svc, folder_id, fn, encrypted)
        pruned = prune_old_backups(svc, folder_id, cfg.get("max_backups", MAX_BACKUPS))

        now                = datetime.now(timezone.utc)
        cfg["last_backup"] = now.isoformat()
        save_config(cfg)

        if not silent:
            print(f"{GREEN}done{RESET}")
            if pruned:
                print(f"  {DIM}Pruned {pruned} old backup(s).{RESET}")
        return now

    except Exception as e:
        if not silent:
            print(f"\n  {RED}Backup failed:{RESET} {e}")
        return None


# -----------------------------------------------------------------------------
# Scheduler
# -----------------------------------------------------------------------------

_scheduler_thread: threading.Thread | None = None
_last_backup_time: datetime | None         = None


def _scheduler_loop(interval_hours: int):
    global _last_backup_time
    interval_secs = interval_hours * 3600
    while True:
        time.sleep(interval_secs)
        result = run_backup(silent=True)
        if result:
            _last_backup_time = result


def start_scheduler(interval_hours: int = None):
    """Start the background backup scheduler. No passphrase needed."""
    global _scheduler_thread
    cfg = load_config()
    if not cfg or not cfg.get("enabled"):
        return
    interval = interval_hours if interval_hours is not None else cfg.get("interval_hours", 4)
    # Persist override so dashboard shows accurate next-backup time
    if interval_hours is not None and interval_hours != cfg.get("interval_hours"):
        cfg["interval_hours"] = interval_hours
        save_config(cfg)
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(interval,),
        daemon=True,
        name="backup-scheduler",
    )
    _scheduler_thread.start()


# -----------------------------------------------------------------------------
# Dashboard helper
# -----------------------------------------------------------------------------

def get_last_backup_str() -> str:
    cfg = load_config()
    if not cfg or not cfg.get("enabled"):
        return f"{DIM}Not configured{RESET}"

    ts_str = cfg.get("last_backup")
    if _last_backup_time:
        ts = _last_backup_time
    elif ts_str:
        try:
            ts = datetime.fromisoformat(ts_str)
        except Exception:
            return "Unknown"
    else:
        return f"{DIM}Never — runs at next interval{RESET}"

    delta = int((datetime.now(timezone.utc) - ts).total_seconds())
    if delta < 60:
        return f"{GREEN}Just now{RESET}"
    elif delta < 3600:
        return f"{delta // 60}min ago"
    elif delta < 86400:
        h = delta // 3600
        m = (delta % 3600) // 60
        return f"{h}h {m:02d}min ago"
    else:
        d = delta // 86400
        h = (delta % 86400) // 3600
        return f"{d}d {h}h ago"


# -----------------------------------------------------------------------------
# Standalone entry point — run this directly to set up or re-configure backups
# -----------------------------------------------------------------------------

def _standalone_main():
    if platform.system() == "Windows":
        os.system("color")

    print(f"{CYAN}{BOLD}")
    print("  fortispass — Backup Setup")
    print(f"{RESET}")
    print(f"  {DIM}{'-' * 44}{RESET}\n")
    print(f"  {YELLOW}Stop the server before continuing if it is currently running.{RESET}")
    print(f"  Run  {BOLD}python tools/stop.py{RESET}  in another terminal, then come back here.\n")

    ready = input("  Is the server stopped? [y/n]: ").strip().lower()
    if ready not in ("y", "yes"):
        print(f"\n  {DIM}Aborted. Stop the server first, then re-run this script.{RESET}\n")
        sys.exit(0)

    cfg = load_config()
    if cfg is not None and cfg.get("enabled"):
        print(f"\n  {GREEN}Backups are already configured and enabled.{RESET}")
        print(f"  To reconfigure, delete {BOLD}.backup_config.json{RESET} and re-run.\n")
        sys.exit(0)

    print()
    result = setup_wizard()
    if result:
        print(f"  {GREEN}[OK]  Done.{RESET} Start the server with  {BOLD}python server.py{RESET}")
        print(f"       to begin automatic backups.\n")
    else:
        print(f"  Exited without enabling backups.\n")


if __name__ == "__main__":
    _standalone_main()
