# Android Folder

This folder contains Android-friendly variants of the schedule tracker.

## Files
- `web_app.py` – **recommended for Termux** (no Kivy required). Runs in your phone browser.
- `run_termux_web.sh` – one-command launcher for the Termux web app.
- `main.py` – Kivy mobile app compatible with the same JSON schedule schema (optional path).
- `buildozer.spec.example` – starter Buildozer config for APK packaging.

## Mobile optimizations included
- Large touch targets for Load/Save/Add actions.
- Vertical, single-column layout for narrow phone screens.
- Scrollable class cards with conflict badges.
- JSON normalization compatible with:
  - root object containing `schedules`
  - each schedule having `name`, optional `source_schedules`, `classes`
  - each class having `class_name`, `section`, `days`, `start_time`, `end_time`, `location`, `teacher`, `credits`, optional `_color`

## Run locally (desktop test)
```bash
python android/main.py
```


## One-command Termux launcher
### Preferred (no Kivy needed)
Use the web launcher from repo root:
```bash
bash android/run_termux_web.sh
```

This starts a local server at `http://127.0.0.1:8765` and opens it in your browser.

### Kivy launcher (optional)
Use the Kivy helper script from repo root:
```bash
bash android/run_termux_x11.sh
```

The script will:
- set `DISPLAY=:0`
- start `termux-x11` if needed
- launch `python android/main.py`

If Kivy is missing, the script will show install instructions.
You can also let it try the Termux package install automatically:
```bash
bash android/run_termux_x11.sh --auto-install-kivy
```

## Termux troubleshooting: `pip install kivy` build failure
On Termux, `pip install kivy` may fail because it tries to compile from source.
Alternative: skip Kivy entirely and use:
```bash
bash android/run_termux_web.sh
```

If you still want Kivy, prefer the prebuilt Termux package:
```bash
pkg install x11-repo
pkg install python-kivy
```

## Build APK (Linux)
1. Install Buildozer prerequisites.
2. Copy example spec:
   ```bash
   cp android/buildozer.spec.example android/buildozer.spec
   ```
3. Build:
   ```bash
   cd android
   buildozer -v android debug
   ```

The app reads/writes `schedules_android.json` in its working directory.
