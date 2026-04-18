# Android Folder

This folder contains a touch-optimized Android variant of the schedule tracker.

## Files
- `main.py` – Kivy mobile app compatible with the same JSON schedule schema.
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
