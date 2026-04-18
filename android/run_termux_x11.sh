#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Termux launcher for Kivy app with Termux:X11
# Usage:
#   bash android/run_termux_x11.sh

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$APP_DIR/.." && pwd)"
AUTO_INSTALL_KIVY="${1:-}"

if ! command -v termux-x11 >/dev/null 2>&1; then
  echo "[ERROR] termux-x11 command not found. Install Termux:X11 app and package first." >&2
  echo "        pkg install x11-repo && pkg install termux-x11-nightly" >&2
  exit 1
fi

if ! command -v python >/dev/null 2>&1; then
  echo "[ERROR] python is not installed. Run: pkg install python" >&2
  exit 1
fi

if ! python -c "import kivy" >/dev/null 2>&1; then
  if [[ "$AUTO_INSTALL_KIVY" == "--auto-install-kivy" ]]; then
    echo "[INFO] Kivy not detected, trying Termux package install..."
    pkg install -y x11-repo >/dev/null 2>&1 || true
    pkg install -y python-kivy
  fi
fi

if ! python -c "import kivy" >/dev/null 2>&1; then
  echo "[ERROR] Kivy is not installed for this Termux Python environment." >&2
  echo "" >&2
  echo "Recommended (Termux package, avoids pip source-build issues):" >&2
  echo "  pkg install x11-repo" >&2
  echo "  pkg install python-kivy" >&2
  echo "" >&2
  echo "Then re-run:" >&2
  echo "  bash android/run_termux_x11.sh" >&2
  echo "" >&2
  echo "Optional: let this script try package install automatically:" >&2
  echo "  bash android/run_termux_x11.sh --auto-install-kivy" >&2
  exit 1
fi

export DISPLAY=:0
export PYTHONUNBUFFERED=1

# Start X11 backend if not already running.
if ! pgrep -f "termux-x11 :0" >/dev/null 2>&1; then
  echo "[INFO] Starting Termux:X11 on display :0"
  termux-x11 :0 >/dev/null 2>&1 &
  sleep 1
else
  echo "[INFO] Termux:X11 already running on :0"
fi

cd "$ROOT_DIR"
echo "[INFO] Launching android/main.py"
python android/main.py
