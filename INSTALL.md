# Build standalone one-file apps (Windows, Debian Linux, and macOS)

This project is a single-file Tkinter app: `schedule_planner.py`.
You can package it as a **single runnable file** with PyInstaller so end users do not need to install Python.

> Build on the same OS you target:
> - Windows build for Windows
> - Linux build for Linux
> - macOS build for macOS

Cross-building is not supported for reliable desktop bundles.

---

## 1) Install build prerequisites

### Windows
1. Install Python 3.11+ from: https://www.python.org/downloads/windows/
2. Check **Add Python to PATH** during install.
3. In Command Prompt:

```bat
python --version
pip --version
pip install --upgrade pip pyinstaller reportlab
```

### Debian / Ubuntu Linux
Install Python + Tk support + build tools:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-tk tk-dev build-essential
python3 -m pip install --user --upgrade pip pyinstaller reportlab
```

If `pyinstaller` is not in PATH, use `python3 -m PyInstaller` in commands below.

### macOS
1. Install Xcode Command Line Tools:

```bash
xcode-select --install
```

2. Install Python (recommended via Homebrew):

```bash
brew install python tcl-tk
python3 -m pip install --upgrade pip pyinstaller reportlab
```

---

## 2) Build one-file app

From the repository root (same folder as `schedule_planner.py`):

### Windows `.exe`

```bat
pyinstaller --noconfirm --clean --windowed --onefile --name SchedulePlanner schedule_planner.py
```

Output:
- `dist\SchedulePlanner.exe`

### Debian/Linux single executable

```bash
pyinstaller --noconfirm --clean --onefile --name schedule-planner schedule_planner.py
```

Output:
- `dist/schedule-planner`

Make it executable (if needed):

```bash
chmod +x dist/schedule-planner
```

### macOS app binary (one-file executable)

```bash
pyinstaller --noconfirm --clean --windowed --onefile --name SchedulePlanner schedule_planner.py
```

Output:
- `dist/SchedulePlanner`

You can run it directly:

```bash
./dist/SchedulePlanner
```

---

## 3) Distribution notes

- **Windows**: ship `SchedulePlanner.exe`.
- **Debian/Linux**: ship `schedule-planner` built on a compatible distro version (prefer older baseline distro for wider glibc compatibility).
- **macOS**: ship `SchedulePlanner` built on the same major macOS version family as target users.

For maximum compatibility, build separately per OS (and architecture, e.g., x86_64 vs arm64).

---

## 4) Optional icon

If you have icon files in repo root:

- Windows: `app.ico`
- macOS: `app.icns`

Examples:

```bat
pyinstaller --noconfirm --clean --windowed --onefile --name SchedulePlanner --icon app.ico schedule_planner.py
```

```bash
pyinstaller --noconfirm --clean --windowed --onefile --name SchedulePlanner --icon app.icns schedule_planner.py
```

---

## 5) Troubleshooting

- **`pyinstaller: command not found`**
  - Use module form:
    - Linux/macOS: `python3 -m PyInstaller ...`
    - Windows: `python -m PyInstaller ...`

- **App fails to launch on Linux due to GLIBC version**
  - Build on an older Debian/Ubuntu base (or in Docker) to improve compatibility with older systems.

- **macOS Gatekeeper warning**
  - Right-click → Open once, or code-sign/notarize for broader distribution.

- **Need debug output**
  - Rebuild without `--windowed` and run from terminal to inspect errors.

---

## 6) Quick commands

### Windows
```bat
pip install --upgrade pip pyinstaller reportlab && pyinstaller --noconfirm --clean --windowed --onefile --name SchedulePlanner schedule_planner.py
```

### Debian/Linux
```bash
python3 -m pip install --user --upgrade pip pyinstaller reportlab && python3 -m PyInstaller --noconfirm --clean --onefile --name schedule-planner schedule_planner.py
```

### macOS
```bash
python3 -m pip install --upgrade pip pyinstaller reportlab && python3 -m PyInstaller --noconfirm --clean --windowed --onefile --name SchedulePlanner schedule_planner.py
```
