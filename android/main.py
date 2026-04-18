"""
Android-optimized Schedule Tracker (Kivy)

This mobile variant is designed for touch screens:
- Larger controls and spacing
- Vertical stacked layout for narrow devices
- JSON format compatible with schedule_planner.py
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput


TIME_PATTERN = re.compile(r"^([0-1]?\d|2[0-3]):([0-5]\d)$")
DAY_ORDER = ["M", "T", "W", "Th", "F"]
DEFAULT_PATH = Path("schedules_android.json")


def normalize_time(value: str) -> str | None:
    m = TIME_PATTERN.match(str(value).strip())
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"


def time_to_minutes(value: str) -> int:
    hh, mm = map(int, value.split(":"))
    return hh * 60 + mm


def overlaps(a: dict, b: dict) -> bool:
    if not set(a.get("days", [])) & set(b.get("days", [])):
        return False
    return time_to_minutes(a["start_time"]) < time_to_minutes(b["end_time"]) and time_to_minutes(b["start_time"]) < time_to_minutes(a["end_time"])


def normalize_class(c: dict) -> dict:
    c = dict(c)
    c["class_name"] = str(c.get("class_name", "")).strip()
    c["section"] = str(c.get("section", "")).strip()
    c["days"] = [d for d in c.get("days", []) if d in DAY_ORDER] if isinstance(c.get("days", []), list) else []
    c["start_time"] = normalize_time(c.get("start_time", "00:00")) or "00:00"
    c["end_time"] = normalize_time(c.get("end_time", "00:00")) or "00:00"
    c["location"] = str(c.get("location", "")).strip()
    c["teacher"] = str(c.get("teacher", "")).strip()
    c["credits"] = int(c.get("credits", 0) or 0)
    if c.get("_color"):
        c["_color"] = c["_color"]
    return c


def normalize_data(data: dict) -> dict:
    schedules = data.get("schedules", []) if isinstance(data, dict) else []
    normalized = []
    for idx, s in enumerate(schedules, 1):
        if not isinstance(s, dict):
            continue
        classes = [normalize_class(c) for c in s.get("classes", []) if isinstance(c, dict)]
        normalized.append(
            {
                "name": str(s.get("name") or f"Schedule {idx}"),
                "source_schedules": s.get("source_schedules", []) if isinstance(s.get("source_schedules", []), list) else [],
                "classes": classes,
            }
        )
    return {"schedules": normalized or [{"name": "Default", "source_schedules": [], "classes": []}]}


@dataclass
class MobileState:
    data: dict
    selected: str


class ScheduleMobileRoot(BoxLayout):
    status = StringProperty("Ready")
    schedule_names = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(10), **kwargs)
        self.state = MobileState(data={"schedules": [{"name": "Default", "source_schedules": [], "classes": []}]}, selected="Default")

        top = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        self.spinner = Spinner(text="Default", values=["Default"], size_hint_x=0.55)
        self.spinner.bind(text=lambda *_: self._on_select())
        top.add_widget(self.spinner)
        top.add_widget(Button(text="Load", on_press=lambda *_: self.load_json(), size_hint_x=0.15))
        top.add_widget(Button(text="Save", on_press=lambda *_: self.save_json(), size_hint_x=0.15))
        top.add_widget(Button(text="Add", on_press=lambda *_: self.open_add_popup(), size_hint_x=0.15))
        self.add_widget(top)

        self.scroll = ScrollView()
        self.classes_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6), padding=(0, dp(4)))
        self.classes_box.bind(minimum_height=self.classes_box.setter("height"))
        self.scroll.add_widget(self.classes_box)
        self.add_widget(self.scroll)

        footer = Label(text=self.status, size_hint_y=None, height=dp(30), halign="left", valign="middle")
        footer.bind(size=lambda instance, _: setattr(instance, "text_size", instance.size))
        self.bind(status=lambda *_: setattr(footer, "text", self.status))
        self.add_widget(footer)

        Clock.schedule_once(lambda *_: self.refresh(), 0)

    def _get_selected_schedule(self) -> dict:
        for s in self.state.data.get("schedules", []):
            if s.get("name") == self.state.selected:
                return s
        return self.state.data["schedules"][0]

    def _on_select(self):
        self.state.selected = self.spinner.text
        self.refresh()

    def refresh(self):
        self.spinner.values = [s["name"] for s in self.state.data["schedules"]]
        if self.state.selected not in self.spinner.values:
            self.state.selected = self.spinner.values[0]
        self.spinner.text = self.state.selected

        schedule = self._get_selected_schedule()
        self.classes_box.clear_widgets()
        conflicts = set()
        classes = schedule.get("classes", [])
        for i in range(len(classes)):
            for j in range(i + 1, len(classes)):
                if overlaps(classes[i], classes[j]):
                    conflicts.add(i)
                    conflicts.add(j)

        credits = 0
        for i, c in enumerate(classes):
            credits += int(c.get("credits", 0))
            loc = c.get("location", "").strip() or "N/A"
            conflict_badge = " [CONFLICT]" if i in conflicts else ""
            text = (
                f"[b]{c.get('class_name')} ({c.get('section')})[/b]{conflict_badge}\n"
                f"Days: {' '.join(c.get('days', [])) or 'N/A'}\n"
                f"Time: {c.get('start_time')} - {c.get('end_time')}\n"
                f"Location: {loc}\n"
                f"Teacher: {c.get('teacher', '') or 'N/A'} | Credits: {c.get('credits', 0)}"
            )
            lbl = Label(
                text=text,
                markup=True,
                size_hint_y=None,
                height=dp(108),
                halign="left",
                valign="middle",
                text_size=(self.width - dp(28), None),
            )
            self.classes_box.add_widget(lbl)

        self.status = f"Schedule: {schedule.get('name')}  •  Classes: {len(classes)}  •  Credits: {credits}"

    def load_json(self):
        try:
            raw = json.loads(DEFAULT_PATH.read_text(encoding="utf-8")) if DEFAULT_PATH.exists() else {"schedules": []}
            self.state.data = normalize_data(raw)
            self.state.selected = self.state.data["schedules"][0]["name"]
            self.status = f"Loaded {DEFAULT_PATH.name}"
            self.refresh()
        except Exception as exc:
            self.status = f"Load error: {exc}"

    def save_json(self):
        try:
            DEFAULT_PATH.write_text(json.dumps(self.state.data, indent=2), encoding="utf-8")
            self.status = f"Saved {DEFAULT_PATH.name}"
        except Exception as exc:
            self.status = f"Save error: {exc}"

    def open_add_popup(self):
        content = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        fields = {
            "class_name": TextInput(hint_text="Class Name", multiline=False),
            "section": TextInput(hint_text="Section", multiline=False),
            "days": TextInput(hint_text="Days (comma separated: M,T,W,Th,F)", multiline=False),
            "start_time": TextInput(hint_text="Start (HH:MM)", multiline=False),
            "end_time": TextInput(hint_text="End (HH:MM)", multiline=False),
            "location": TextInput(hint_text="Location", multiline=False),
            "teacher": TextInput(hint_text="Teacher", multiline=False),
            "credits": TextInput(hint_text="Credits", multiline=False),
        }
        for w in fields.values():
            w.size_hint_y = None
            w.height = dp(42)
            content.add_widget(w)

        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        popup = Popup(title="Add Class", content=content, size_hint=(0.96, 0.9))

        def submit(*_):
            try:
                class_name = fields["class_name"].text.strip()
                section = fields["section"].text.strip()
                start = normalize_time(fields["start_time"].text.strip())
                end = normalize_time(fields["end_time"].text.strip())
                days = [d.strip() for d in fields["days"].text.split(",") if d.strip() in DAY_ORDER]
                location = fields["location"].text.strip()
                teacher = fields["teacher"].text.strip()
                credits = int(fields["credits"].text.strip() or "0")
                if not (class_name and section and start and end):
                    raise ValueError("Missing required class fields.")
                if days and time_to_minutes(start) >= time_to_minutes(end):
                    raise ValueError("End time must be after start time for classes with days.")
                if not days and not (start == "00:00" and end == "00:00"):
                    raise ValueError("Classes without days must be 00:00-00:00.")

                self._get_selected_schedule()["classes"].append(
                    {
                        "class_name": class_name,
                        "section": section,
                        "days": days,
                        "start_time": start,
                        "end_time": end,
                        "location": location,
                        "teacher": teacher,
                        "credits": credits,
                    }
                )
                popup.dismiss()
                self.status = "Class added"
                self.refresh()
            except Exception as exc:
                self.status = f"Add failed: {exc}"

        btns.add_widget(Button(text="Cancel", on_press=lambda *_: popup.dismiss()))
        btns.add_widget(Button(text="Save", on_press=submit))
        content.add_widget(btns)
        popup.open()


class ScheduleMobileApp(App):
    def build(self):
        self.title = "Schedule Tracker Mobile"
        return ScheduleMobileRoot()


if __name__ == "__main__":
    ScheduleMobileApp().run()
