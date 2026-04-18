"""
Termux-friendly web version of Schedule Tracker.
No Kivy required: uses only Python standard library.

Run:
    python android/web_app.py
Then open http://127.0.0.1:8765 in your Android browser.
"""

from __future__ import annotations

import html
import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DATA_PATH = Path("schedules_android.json")
SAMPLE_PATH = Path("sample_schedules.json")
HOST = "127.0.0.1"
PORT = 8765
TIME_PATTERN = re.compile(r"^([0-1]?\d|2[0-3]):([0-5]\d)$")
DAY_ORDER = ["M", "T", "W", "Th", "F"]


def normalize_time(value: str) -> str | None:
    match = TIME_PATTERN.match(str(value or "").strip())
    if not match:
        return None
    hh, mm = int(match.group(1)), int(match.group(2))
    return f"{hh:02d}:{mm:02d}"


def normalize_class(c: dict) -> dict:
    days = c.get("days", [])
    if not isinstance(days, list):
        days = []
    return {
        "class_name": str(c.get("class_name", "")).strip(),
        "section": str(c.get("section", "")).strip(),
        "days": [d for d in days if d in DAY_ORDER],
        "start_time": normalize_time(c.get("start_time", "00:00")) or "00:00",
        "end_time": normalize_time(c.get("end_time", "00:00")) or "00:00",
        "location": str(c.get("location", "")).strip(),
        "teacher": str(c.get("teacher", "")).strip(),
        "credits": int(c.get("credits", 0) or 0),
    }


def normalize_data(payload: dict) -> dict:
    schedules = payload.get("schedules", []) if isinstance(payload, dict) else []
    out = []
    for i, schedule in enumerate(schedules, start=1):
        if not isinstance(schedule, dict):
            continue
        classes = schedule.get("classes", []) if isinstance(schedule.get("classes", []), list) else []
        out.append(
            {
                "name": str(schedule.get("name") or f"Schedule {i}").strip() or f"Schedule {i}",
                "source_schedules": schedule.get("source_schedules", []) if isinstance(schedule.get("source_schedules", []), list) else [],
                "classes": [normalize_class(c) for c in classes if isinstance(c, dict)],
            }
        )
    if not out:
        out = [{"name": "Default", "source_schedules": [], "classes": []}]
    return {"schedules": out}


def load_data() -> dict:
    if DATA_PATH.exists():
        try:
            return normalize_data(json.loads(DATA_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    # First-run fallback: bootstrap from repository sample file if present.
    if SAMPLE_PATH.exists():
        try:
            sample = normalize_data(json.loads(SAMPLE_PATH.read_text(encoding="utf-8")))
            save_data(sample)
            return sample
        except Exception:
            pass
    return {"schedules": [{"name": "Default", "source_schedules": [], "classes": []}]}


def save_data(data: dict) -> None:
    DATA_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def page_html(data: dict, selected: str, message: str = "") -> str:
    schedules = data["schedules"]
    names = [s["name"] for s in schedules]
    if selected not in names:
        selected = names[0]
    schedule = next(s for s in schedules if s["name"] == selected)

    options = "".join(
        f"<option value='{html.escape(n)}' {'selected' if n == selected else ''}>{html.escape(n)}</option>"
        for n in names
    )

    rows = []
    total_credits = 0
    for c in schedule.get("classes", []):
        total_credits += int(c.get("credits", 0))
        rows.append(
            "<tr>"
            f"<td>{html.escape(c.get('class_name', ''))}</td>"
            f"<td>{html.escape(c.get('section', ''))}</td>"
            f"<td>{html.escape(' '.join(c.get('days', [])) or 'N/A')}</td>"
            f"<td>{html.escape(c.get('start_time', ''))}</td>"
            f"<td>{html.escape(c.get('end_time', ''))}</td>"
            f"<td>{html.escape(c.get('location', '') or 'N/A')}</td>"
            f"<td>{html.escape(c.get('teacher', '') or 'N/A')}</td>"
            f"<td>{int(c.get('credits', 0))}</td>"
            "</tr>"
        )
    table_rows = "".join(rows) if rows else "<tr><td colspan='8'>No classes</td></tr>"

    return f"""
<!doctype html>
<html>
<head>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Schedule Tracker (Web)</title>
<style>
body{{font-family:Arial,sans-serif;margin:12px;background:#f7f7f7;}}
.card{{background:#fff;border-radius:10px;padding:12px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.1);}}
input,select,button{{font-size:16px;padding:10px;margin:4px 0;width:100%;box-sizing:border-box;}}
table{{width:100%;border-collapse:collapse;font-size:13px;}}
th,td{{border:1px solid #ddd;padding:6px;text-align:left;}}
.msg{{color:#0b6;min-height:20px;}}
</style>
</head>
<body>
<div class='card'>
  <h2>Schedule Tracker (Termux Web)</h2>
  <div class='msg'>{html.escape(message)}</div>
  <form method='get'>
    <label>Schedule</label>
    <select name='s'>{options}</select>
    <button type='submit'>Switch Schedule</button>
  </form>
  <p><b>Total Credits:</b> {total_credits}</p>
</div>

<div class='card'>
  <h3>Classes in {html.escape(selected)}</h3>
  <table>
    <tr><th>Class</th><th>Section</th><th>Days</th><th>Start</th><th>End</th><th>Location</th><th>Teacher</th><th>Credits</th></tr>
    {table_rows}
  </table>
</div>

<div class='card'>
  <h3>Add Class</h3>
  <form method='post' action='/add-class'>
    <input type='hidden' name='selected' value='{html.escape(selected)}'>
    <input name='class_name' placeholder='Class Name' required>
    <input name='section' placeholder='Section' required>
    <input name='days' placeholder='Days comma-separated (M,T,W,Th,F)'>
    <input name='start_time' placeholder='Start (HH:MM)' required>
    <input name='end_time' placeholder='End (HH:MM)' required>
    <input name='location' placeholder='Location'>
    <input name='teacher' placeholder='Teacher'>
    <input name='credits' placeholder='Credits' value='0' required>
    <button type='submit'>Add Class</button>
  </form>
</div>

<div class='card'>
  <h3>Add Schedule</h3>
  <form method='post' action='/add-schedule'>
    <input name='name' placeholder='New schedule name' required>
    <button type='submit'>Create Schedule</button>
  </form>
</div>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = load_data()
        selected = parse_qs(urlparse(self.path).query).get("s", [data["schedules"][0]["name"]])[0]
        self._send_html(page_html(data, selected))

    def do_POST(self):
        data = load_data()
        content_len = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_len).decode("utf-8")
        form = {k: v[0] for k, v in parse_qs(raw).items()}
        message = "Saved"
        selected = form.get("selected") or data["schedules"][0]["name"]

        if self.path == "/add-schedule":
            name = form.get("name", "").strip()
            if name and all(s["name"] != name for s in data["schedules"]):
                data["schedules"].append({"name": name, "source_schedules": [], "classes": []})
                selected = name
                message = f"Created schedule: {name}"
            else:
                message = "Schedule name already exists or is invalid"
        elif self.path == "/add-class":
            try:
                schedule = next(s for s in data["schedules"] if s["name"] == selected)
                days = [d.strip() for d in form.get("days", "").split(",") if d.strip() in DAY_ORDER]
                start = normalize_time(form.get("start_time", ""))
                end = normalize_time(form.get("end_time", ""))
                if not start or not end:
                    raise ValueError("Invalid time format")
                if days and start >= end:
                    raise ValueError("End time must be after start time")
                if not days and not (start == "00:00" and end == "00:00"):
                    raise ValueError("No-day classes must use 00:00-00:00")
                schedule["classes"].append(
                    {
                        "class_name": form.get("class_name", "").strip(),
                        "section": form.get("section", "").strip(),
                        "days": days,
                        "start_time": start,
                        "end_time": end,
                        "location": form.get("location", "").strip(),
                        "teacher": form.get("teacher", "").strip(),
                        "credits": int(form.get("credits", "0") or "0"),
                    }
                )
                message = "Class added"
            except Exception as exc:
                message = f"Error: {exc}"

        save_data(data)
        self._send_html(page_html(data, selected, message))

    def log_message(self, format, *args):
        return

    def _send_html(self, content: str):
        body = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    print(f"[INFO] Starting web app on http://{HOST}:{PORT}")
    print("[INFO] Press Ctrl+C to stop")
    with ThreadingHTTPServer((HOST, PORT), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
