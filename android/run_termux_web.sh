#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$APP_DIR/.." && pwd)"

if ! command -v python >/dev/null 2>&1; then
  echo "[ERROR] python is not installed. Run: pkg install python" >&2
  exit 1
fi

cd "$ROOT_DIR"
echo "[INFO] Starting Termux web app at http://127.0.0.1:8765"
if command -v termux-open-url >/dev/null 2>&1; then
  termux-open-url "http://127.0.0.1:8765" >/dev/null 2>&1 || true
fi
python android/web_app.py
