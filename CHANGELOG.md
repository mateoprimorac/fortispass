# Changelog

## 1.0.1

### Android app

- Renamed the Android theme family from `Theme.Biokey...` to `Theme.Fortispass...` across the manifest, theme resources, and `ThemeManager`.
- Added footer-style GitHub repository access and version/codename labels to:
  - the setup screen
  - the logged-in main menu
- Added a GitHub icon drawable for the Android footer button.
- Updated setup-screen behavior so `Device Name` is required before vault creation.
- Updated setup/main screen footer styling and placement for the GitHub link and version display.

### Browser extension

- Minor UI changes.

### Server and local tooling

- Improved `server.py` handling for non-interactive/background runs.
- Introduced panel-opening flow for already-running instances, including the panel loading/attach behavior.
- Added a 10s timer before confirmation on the `--wipe` flag.
- Source changes were also made in maintenance tooling:
  - `tools/backup.py`
  - `tools/generate_secrets.py`
  - `tools/restore.py`
  - `tools/stop.py`

### Project/config changes

- Added `.gitignore`.
- Removed old docs present in the 1.0.0 tree:
  - `docs/COMPATIBILITY.md`
  - `docs/THREAT_MODEL.md`

### Documentation

- Updated `README.md`.

