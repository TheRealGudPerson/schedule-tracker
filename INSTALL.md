# Build a standalone Windows `.exe` (no Python required on target machine)

This project is a single-file Tkinter app (`schedule_planner.py`).
To create a Windows executable that runs on a Windows PC **without installing Python**, build it on a Windows machine with PyInstaller.

> Important: Build on the same OS you target. A Linux-built executable will not run on Windows.

## 1) On a Windows machine, install Python

1. Download Python 3.11+ from https://www.python.org/downloads/windows/
2. During install, check **Add Python to PATH**.
3. Open **Command Prompt** and verify:

```bat
python --version
pip --version
```

## 2) Get this project and install build dependency

From Command Prompt in the project folder:

```bat
pip install --upgrade pip
pip install pyinstaller reportlab
```

## 3) Build the `.exe`

From the folder containing `schedule_planner.py`:

```bat
pyinstaller --noconfirm --clean --windowed --onefile --name SchedulePlanner schedule_planner.py
```

## 4) Find the executable

After build completes, use:

- `dist\SchedulePlanner.exe`

Copy that `.exe` to any Windows machine and run it directly.
No Python installation is needed on the target machine.

## 5) Optional: Include app icon

If you have `app.ico` in the repo root:

```bat
pyinstaller --noconfirm --clean --windowed --onefile --name SchedulePlanner --icon app.ico schedule_planner.py
```

## 6) Optional: Reduce antivirus false positives

Some one-file executables can trigger false positives. If needed:

- Rebuild without `--onefile` (folder mode):

```bat
pyinstaller --noconfirm --clean --windowed --name SchedulePlanner schedule_planner.py
```

- Code-sign `SchedulePlanner.exe`.

## 7) Troubleshooting

- **`pyinstaller` not found**
  - Run with module form: `python -m PyInstaller ...`
- **Missing module at runtime**
  - Reinstall dependencies and rebuild:
    `pip install --upgrade pyinstaller reportlab`
- **Executable opens then immediately closes**
  - Build once without `--windowed` to see console errors:

```bat
pyinstaller --noconfirm --clean --onefile --name SchedulePlanner schedule_planner.py
```

Then run `dist\SchedulePlanner.exe` from Command Prompt to read the traceback.

## 8) Reproducible quick build command

```bat
pip install --upgrade pip pyinstaller reportlab && pyinstaller --noconfirm --clean --windowed --onefile --name SchedulePlanner schedule_planner.py
```
