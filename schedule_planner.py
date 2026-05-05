import copy
import json
import re
from dataclasses import dataclass
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
from tkinter import simpledialog

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas as pdf_canvas


TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
FLEX_TIME_PATTERN = re.compile(r"^([0-1]?\d|2[0-3]):([0-5]\d)$")
DAY_ORDER = ["M", "T", "W", "Th", "F"]
DEFAULT_JSON = {"schedules": [{"name": "Default", "classes": []}]}
REQUIRED_CLASS_KEYS = [
    "class_name",
    "section",
    "days",
    "start_time",
    "end_time",
    "location",
    "teacher",
    "credits",
]
REQUIRED_MEETING_KEYS = ["days", "start_time", "end_time", "location"]


@dataclass
class Layout:
    header_h: int = 36
    time_col_w: int = 90
    day_col_w: int = 160
    row_h: int = 60
    start_hour: int = 8
    end_hour: int = 20


def validate_time(value: str) -> bool:
    return bool(TIME_PATTERN.match(value))


def normalize_time_string(value: str) -> str | None:
    raw = str(value or "").strip()
    match = FLEX_TIME_PATTERN.match(raw)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    return f"{hour:02d}:{minute:02d}"


def time_to_minutes(value: str) -> int:
    normalized = normalize_time_string(value)
    if not normalized:
        raise ValueError(f"Invalid time '{value}'. Expected HH:MM in 24-hour format.")
    hours, minutes = map(int, normalized.split(":"))
    return hours * 60 + minutes


def minutes_to_ampm(total_minutes: int) -> str:
    hour = (total_minutes // 60) % 24
    minute = total_minutes % 60
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour:02d}:{minute:02d} {suffix}"


def hhmm_to_ampm(value: str) -> str:
    return minutes_to_ampm(time_to_minutes(value))


def classes_overlap(a: dict, b: dict) -> bool:
    if not set(a.get("days", [])) & set(b.get("days", [])):
        return False
    a_start, a_end = time_to_minutes(a["start_time"]), time_to_minutes(a["end_time"])
    b_start, b_end = time_to_minutes(b["start_time"]), time_to_minutes(b["end_time"])
    return a_start < b_end and b_start < a_end


def normalize_meeting_entry(raw: dict, fallback_location: str = "") -> dict:
    item = dict(raw or {})
    days = item.get("days", [])
    if not isinstance(days, list):
        days = []
    return {
        "days": [d for d in days if d in DAY_ORDER],
        "start_time": normalize_time_string(item.get("start_time")) or "00:00",
        "end_time": normalize_time_string(item.get("end_time")) or "00:00",
        "location": str(item.get("location", fallback_location)).strip(),
    }


def expand_class_meetings(class_item: dict) -> list[dict]:
    meetings = class_item.get("meetings")
    if isinstance(meetings, list) and meetings:
        expanded = [normalize_meeting_entry(m, class_item.get("location", "")) for m in meetings if isinstance(m, dict)]
    else:
        expanded = [
            normalize_meeting_entry(
                {
                    "days": class_item.get("days", []),
                    "start_time": class_item.get("start_time", "00:00"),
                    "end_time": class_item.get("end_time", "00:00"),
                    "location": class_item.get("location", ""),
                }
            )
        ]
    return expanded


def find_conflicting_indices(classes: list[dict]) -> set[int]:
    conflicts: set[int] = set()
    for i in range(len(classes)):
        for j in range(i + 1, len(classes)):
            try:
                if class_items_overlap(classes[i], classes[j]):
                    conflicts.add(i)
                    conflicts.add(j)
            except Exception:
                continue
    return conflicts


def compute_day_side_by_side_layout(classes: list[dict], day: str) -> tuple[dict[int, tuple[int, int]], dict[int, int]]:
    """
    Returns:
      - placements: class_index -> (slot_index, cluster_id)
      - cluster_widths: cluster_id -> number_of_columns_needed
    """
    day_items = []
    for idx, cls in enumerate(classes):
        if day not in cls.get("days", []):
            continue
        try:
            start = time_to_minutes(cls["start_time"])
            end = time_to_minutes(cls["end_time"])
        except Exception:
            continue
        if end <= start:
            continue
        day_items.append((idx, start, end))

    day_items.sort(key=lambda x: (x[1], x[2], x[0]))
    placements: dict[int, tuple[int, int]] = {}
    cluster_widths: dict[int, int] = {}

    active: list[tuple[int, int]] = []  # (end, slot)
    current_cluster = -1
    for idx, start, end in day_items:
        active = [(e, s) for e, s in active if e > start]
        used_slots = {slot for _, slot in active}

        if not active:
            current_cluster += 1

        slot = 0
        while slot in used_slots:
            slot += 1
        active.append((end, slot))
        placements[idx] = (slot, current_cluster)
        cluster_widths[current_cluster] = max(cluster_widths.get(current_cluster, 0), len(used_slots) + 1)

    return placements, cluster_widths


def normalize_class_entry(raw: dict) -> dict:
    item = dict(raw or {})
    normalized = {k: item.get(k) for k in REQUIRED_CLASS_KEYS}
    normalized["class_name"] = str(normalized.get("class_name") or "").strip()
    normalized["section"] = str(normalized.get("section") or "").strip()
    normalized["location"] = str(normalized.get("location") or "").strip()
    normalized["teacher"] = str(normalized.get("teacher") or "").strip()

    days = normalized.get("days")
    if not isinstance(days, list):
        days = []
    normalized["days"] = [d for d in days if d in DAY_ORDER]

    start = normalize_time_string(normalized.get("start_time")) or "00:00"
    end = normalize_time_string(normalized.get("end_time")) or "00:00"
    normalized["start_time"] = start
    normalized["end_time"] = end

    try:
        normalized["credits"] = int(normalized.get("credits", 0))
    except Exception:
        normalized["credits"] = 0

    raw_meetings = item.get("meetings")
    if isinstance(raw_meetings, list) and raw_meetings:
        normalized["meetings"] = [normalize_meeting_entry(m, normalized["location"]) for m in raw_meetings if isinstance(m, dict)]
    else:
        normalized["meetings"] = expand_class_meetings(normalized)

    if "_color" in item and item["_color"]:
        normalized["_color"] = item["_color"]
    return normalized


def normalize_data_model(data: dict) -> dict:
    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULT_JSON)

    schedules = data.get("schedules")
    if not isinstance(schedules, list):
        return copy.deepcopy(DEFAULT_JSON)

    cleaned_schedules = []
    for i, raw_schedule in enumerate(schedules, start=1):
        if not isinstance(raw_schedule, dict):
            continue
        name = str(raw_schedule.get("name") or f"Schedule {i}").strip() or f"Schedule {i}"
        classes = raw_schedule.get("classes", [])
        if not isinstance(classes, list):
            classes = []

        schedule = {
            "name": name,
            "classes": [normalize_class_entry(c) for c in classes if isinstance(c, dict)],
        }
        sources = raw_schedule.get("source_schedules")
        if isinstance(sources, list):
            schedule["source_schedules"] = [str(s).strip() for s in sources if str(s).strip()]
        if raw_schedule.get("is_comparison_pair"):
            schedule["is_comparison_pair"] = True
        cleaned_schedules.append(schedule)

    if not cleaned_schedules:
        return copy.deepcopy(DEFAULT_JSON)
    return {"schedules": cleaned_schedules}


def location_or_na(class_item: dict) -> str:
    location = str(class_item.get("location", "")).strip()
    return location if location else "N/A"


def class_items_overlap(a: dict, b: dict) -> bool:
    for ma in expand_class_meetings(a):
        for mb in expand_class_meetings(b):
            if classes_overlap(ma, mb):
                return True
    return False


class AddClassDialog(tk.Toplevel):
    def __init__(self, master, on_submit):
        super().__init__(master)
        self.title("Add Class")
        self.resizable(False, False)
        self.on_submit = on_submit
        self.day_vars: dict[str, tk.BooleanVar] = {d: tk.BooleanVar(value=False) for d in DAY_ORDER}

        self.entries: dict[str, tk.Entry] = {}
        fields = [
            ("Class Name", "class_name"),
            ("Section", "section"),
            ("Start Time (HH:MM)", "start_time"),
            ("End Time (HH:MM)", "end_time"),
            ("Location", "location"),
            ("Teacher", "teacher"),
            ("Credits", "credits"),
            ("Color (optional)", "_color"),
        ]

        for idx, (label, key) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=idx, column=0, sticky="w", padx=8, pady=4)
            entry = ttk.Entry(self, width=30)
            entry.grid(row=idx, column=1, sticky="ew", padx=8, pady=4)
            self.entries[key] = entry

        days_row = len(fields)
        ttk.Label(self, text="Days").grid(row=days_row, column=0, sticky="nw", padx=8, pady=4)
        day_frame = ttk.Frame(self)
        day_frame.grid(row=days_row, column=1, sticky="w", padx=8, pady=4)
        for col, day in enumerate(DAY_ORDER):
            ttk.Checkbutton(day_frame, text=day, variable=self.day_vars[day]).grid(row=0, column=col, padx=2)

        btn_row = days_row + 1
        button_frame = ttk.Frame(self)
        button_frame.grid(row=btn_row, column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text="Add", command=self.submit).grid(row=0, column=0, padx=6)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).grid(row=0, column=1, padx=6)

        self.grab_set()

    def submit(self):
        days = [d for d, var in self.day_vars.items() if var.get()]
        payload = {k: e.get().strip() for k, e in self.entries.items()}
        required = ["class_name", "section", "start_time", "end_time", "location", "teacher", "credits"]
        for field in required:
            if not payload[field]:
                messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required.")
                return

        start_normalized = normalize_time_string(payload["start_time"])
        end_normalized = normalize_time_string(payload["end_time"])
        if not start_normalized or not end_normalized:
            messagebox.showerror("Validation Error", "Times must be HH:MM in 24-hour format.")
            return
        payload["start_time"] = start_normalized
        payload["end_time"] = end_normalized

        start_minutes = time_to_minutes(payload["start_time"])
        end_minutes = time_to_minutes(payload["end_time"])
        if days and start_minutes >= end_minutes:
            messagebox.showerror("Validation Error", "For scheduled classes, end time must be later than start time.")
            return
        if not days and (payload["start_time"] != "00:00" or payload["end_time"] != "00:00"):
            messagebox.showerror("Validation Error", "Classes with no meeting days must use 00:00 for both times.")
            return

        try:
            payload["credits"] = int(payload["credits"])
            if payload["credits"] < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validation Error", "Credits must be a non-negative integer.")
            return

        payload["days"] = days
        if not payload.get("_color"):
            payload.pop("_color", None)

        self.on_submit(payload)
        self.destroy()


class SchedulePlannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("College Schedule Planner")
        self.layout = Layout()
        self.data = copy.deepcopy(DEFAULT_JSON)
        self.selected_schedule_name = tk.StringVar(value=self.data["schedules"][0]["name"])
        self.compare_alt_mode = tk.BooleanVar(value=False)
        self.compare_color_a = "#8ecbff"
        self.compare_color_b = "#ffcf8e"

        self.setup_ui()
        self.refresh_schedule_dropdown()
        self.redraw_views()

    @staticmethod
    def is_comparison_pair_schedule(schedule: dict | None) -> bool:
        if not schedule:
            return False
        return bool(schedule.get("is_comparison_pair")) or str(schedule.get("name", "")).startswith("comparison_pair_")

    def setup_ui(self):
        controls = ttk.Frame(self.root)
        controls.pack(fill="x", padx=8, pady=8)

        ttk.Label(controls, text="Schedule:").pack(side="left")
        self.schedule_combo = ttk.Combobox(
            controls,
            textvariable=self.selected_schedule_name,
            state="readonly",
            width=25,
        )
        self.schedule_combo.pack(side="left", padx=4)
        self.schedule_combo.bind("<<ComboboxSelected>>", lambda _: self.redraw_views())

        buttons = [
            ("New", self.create_schedule),
            ("Delete", self.delete_schedule),
            ("Add Class", self.open_add_class_dialog),
            ("Combine", self.combine_schedules),
            ("Compare", self.compare_schedules_window),
            ("Merge Overlaps", self.merge_overlaps),
            ("Smart Generate", self.smart_generate),
            ("Save JSON", self.save_json),
            ("Load JSON", self.load_json),
        ]
        for label, cmd in buttons:
            ttk.Button(controls, text=label, command=cmd).pack(side="left", padx=3)
        ttk.Button(controls, text="Rename", command=self.rename_current_schedule).pack(side="left", padx=3)
        self.export_pdf_btn = ttk.Button(controls, text="Export PDF", command=self.export_pdf)
        self.export_pdf_btn.pack(side="left", padx=3)
        self.export_compare_pdf_btn = ttk.Button(controls, text="Export Compare PDF", command=self.export_pdf)
        ttk.Checkbutton(controls, text="Compare Palette Mode", variable=self.compare_alt_mode, command=self.on_compare_mode_toggle).pack(side="left", padx=6)
        ttk.Button(controls, text="Set Compare Colors", command=self.pick_compare_colors).pack(side="left", padx=3)

        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=8, pady=8)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Schedule Details").pack(anchor="w")
        self.text = tk.Text(left, width=50, wrap="word")
        self.text.pack(fill="both", expand=True)

        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ttk.Label(right, text="Weekly Grid").pack(anchor="w")

        width = self.layout.time_col_w + self.layout.day_col_w * 5
        height = self.layout.header_h + (self.layout.end_hour - self.layout.start_hour) * self.layout.row_h
        self.canvas = tk.Canvas(right, width=width, height=height, bg="white")
        self.canvas.pack(fill="both", expand=True)

    def on_compare_mode_toggle(self):
        if self.compare_alt_mode.get():
            self.export_pdf_btn.pack_forget()
            self.export_compare_pdf_btn.pack(side="left", padx=3)
        else:
            self.export_compare_pdf_btn.pack_forget()
            self.export_pdf_btn.pack(side="left", padx=3)
        self.redraw_views()

    def pick_compare_colors(self):
        c1 = colorchooser.askcolor(title="Select color for first compared schedule", color=self.compare_color_a)[1]
        if c1:
            self.compare_color_a = c1
        c2 = colorchooser.askcolor(title="Select color for second compared schedule", color=self.compare_color_b)[1]
        if c2:
            self.compare_color_b = c2
        self.redraw_views()

    def rename_current_schedule(self):
        schedule = self.get_selected_schedule()
        if not schedule:
            messagebox.showerror("Error", "No schedule selected.")
            return

        current_name = str(schedule.get("name", "")).strip() or "Untitled"
        new_name = simpledialog.askstring("Rename Schedule", "New schedule name:", initialvalue=current_name, parent=self.root)
        if new_name is None:
            return
        new_name = new_name.strip()
        if not new_name:
            messagebox.showerror("Error", "Schedule name cannot be empty.")
            return
        if new_name != current_name and any(s.get("name") == new_name for s in self.data.get("schedules", [])):
            messagebox.showerror("Error", "A schedule with that name already exists.")
            return

        schedule["name"] = new_name
        self.selected_schedule_name.set(new_name)
        self.refresh_schedule_dropdown()
        self.redraw_views()

    def get_selected_schedule(self):
        selected = self.selected_schedule_name.get()
        for schedule in self.data.get("schedules", []):
            if schedule.get("name") == selected:
                return schedule
        if self.data.get("schedules"):
            self.selected_schedule_name.set(self.data["schedules"][0]["name"])
            return self.data["schedules"][0]
        return None

    def refresh_schedule_dropdown(self):
        names = [s.get("name", "Untitled") for s in self.data.get("schedules", [])]
        self.schedule_combo["values"] = names
        if names and self.selected_schedule_name.get() not in names:
            self.selected_schedule_name.set(names[0])

    def redraw_views(self):
        self.update_text_panel()
        self.draw_grid()

    def update_text_panel(self):
        schedule = self.get_selected_schedule()
        self.text.delete("1.0", tk.END)
        self.text.tag_configure("online_header", background="#fff3bf", foreground="#7a5200", font=("Arial", 10, "bold"))
        if not schedule:
            self.text.insert(tk.END, "No schedule selected.")
            return

        classes = schedule.get("classes", [])
        credits_total = 0
        in_person_lines = []
        online_lines = []
        lines = [f"Schedule: {schedule.get('name', 'Untitled')}\n"]
        if schedule.get("source_schedules"):
            lines.append(f"Source schedules: {', '.join(schedule['source_schedules'])}\n")
        lines.append("-" * 50 + "\n")

        is_compare_palette = self.compare_alt_mode.get() and self.is_comparison_pair_schedule(schedule)
        for idx, c in enumerate(classes, start=1):
            credits_total += int(c.get("credits", 0))
            meetings = expand_class_meetings(c)
            meeting_lines = []
            for m in meetings:
                days = " ".join(m.get("days", [])) or "N/A"
                start_ampm = hhmm_to_ampm(m["start_time"])
                end_ampm = hhmm_to_ampm(m["end_time"])
                meeting_lines.append(f"   Meeting: {days} | {start_ampm} - {end_ampm} | {location_or_na(m)}")
            header = f"{idx}. {c.get('class_name')}"
            if not is_compare_palette:
                header += f" ({c.get('section')})"
            rendered = (
                header + "\n"
                + "\n".join(meeting_lines) + "\n"
                f"   Instructor: {c.get('teacher')}\n"
                f"   Credits: {c.get('credits')}\n\n"
            )
            is_online = all((not m.get("days")) and m.get("start_time") == "00:00" and m.get("end_time") == "00:00" for m in meetings)
            if is_online:
                online_lines.append(rendered)
            else:
                in_person_lines.append(rendered)

        lines.append("In-Person Classes\n")
        lines.append("".join(in_person_lines) if in_person_lines else "None\n\n")
        lines.append("ONLINE CLASSES (Highlighted)\n")
        lines.append("".join(online_lines) if online_lines else "None\n")
        lines.append(f"Total Credits: {credits_total}\n")
        content = "".join(lines)
        self.text.insert(tk.END, content)
        marker = "ONLINE CLASSES (Highlighted)"
        start_idx = self.text.search(marker, "1.0", tk.END)
        if start_idx:
            end_idx = f"{start_idx}+{len(marker)}c"
            self.text.tag_add("online_header", start_idx, end_idx)

        if is_compare_palette:
            sources = schedule.get("source_schedules", ["Schedule A", "Schedule B"])
            self.text.insert(tk.END, f"\nLegend:\n■ {sources[0]}\n■ {sources[-1]}\n")
            self.text.tag_configure("legend_a", background=self.compare_color_a)
            self.text.tag_configure("legend_b", background=self.compare_color_b)
            l1 = self.text.search("■", "1.0", tk.END)
            if l1:
                self.text.tag_add("legend_a", l1, f"{l1}+1c")
                l2 = self.text.search("■", f"{l1}+1c", tk.END)
                if l2:
                    self.text.tag_add("legend_b", l2, f"{l2}+1c")

            self.text.tag_configure("cmp_a", background=self.compare_color_a)
            self.text.tag_configure("cmp_b", background=self.compare_color_b)
            for idx, c in enumerate(classes, start=1):
                marker_line = f"{idx}. {c.get('class_name')}"
                pos = self.text.search(marker_line, "1.0", tk.END)
                if pos:
                    end = self.text.index(f"{pos} lineend")
                    tag = "cmp_a" if c.get("_compare_source", 0) == 0 else "cmp_b"
                    self.text.tag_add(tag, pos, end)

    def draw_grid(self):
        self.canvas.delete("all")
        lay = self.layout
        w = lay.time_col_w + lay.day_col_w * 5
        h = lay.header_h + (lay.end_hour - lay.start_hour) * lay.row_h

        self.canvas.create_rectangle(0, 0, w, h, outline="black")

        headers = ["Time", "M", "T", "W", "Th", "F"]
        for col in range(6):
            x = lay.time_col_w if col == 1 else (lay.time_col_w + lay.day_col_w * (col - 1) if col > 1 else 0)
            if col == 0:
                x = lay.time_col_w
            self.canvas.create_line(x, 0, x, h, fill="#ccc")

        for i, label in enumerate(headers):
            if i == 0:
                x0, x1 = 0, lay.time_col_w
            else:
                x0 = lay.time_col_w + (i - 1) * lay.day_col_w
                x1 = x0 + lay.day_col_w
            self.canvas.create_rectangle(x0, 0, x1, lay.header_h, fill="#f0f0f0", outline="black")
            self.canvas.create_text((x0 + x1) / 2, lay.header_h / 2, text=label, font=("Arial", 10, "bold"))

        for hr in range(lay.start_hour, lay.end_hour + 1):
            y = lay.header_h + (hr - lay.start_hour) * lay.row_h
            self.canvas.create_line(0, y, w, y, fill="#ddd")
            minutes = hr * 60
            self.canvas.create_text(
                lay.time_col_w - 6,
                y,
                text=minutes_to_ampm(minutes),
                font=("Arial", 9),
                anchor="e",
            )

        schedule = self.get_selected_schedule()
        if not schedule:
            return

        classes = schedule.get("classes", [])
        conflicts = find_conflicting_indices(classes)
        is_comparison_schedule = self.is_comparison_pair_schedule(schedule)
        use_compare_palette = is_comparison_schedule and self.compare_alt_mode.get()
        use_compare_palette = is_comparison_schedule and self.compare_alt_mode.get()
        day_to_idx = {d: i for i, d in enumerate(DAY_ORDER)}
        expanded_blocks = []
        for class_idx, cls in enumerate(classes):
            for meeting in expand_class_meetings(cls):
                block = dict(meeting)
                block["_class_idx"] = class_idx
                block["_class_ref"] = cls
                expanded_blocks.append(block)

        day_layouts = {day: compute_day_side_by_side_layout(expanded_blocks, day) for day in DAY_ORDER}

        for block_idx, meeting in enumerate(expanded_blocks):
            cls = meeting["_class_ref"]
            class_idx = meeting["_class_idx"]
            start = time_to_minutes(meeting["start_time"])
            end = time_to_minutes(meeting["end_time"])
            for day in meeting.get("days", []):
                if day not in day_to_idx:
                    continue
                day_index = day_to_idx[day]
                placements, cluster_widths = day_layouts[day]
                slot, cluster = placements.get(block_idx, (0, 0))
                slot_count = max(cluster_widths.get(cluster, 1), 1)
                usable_w = lay.day_col_w - 4
                slot_w = usable_w / slot_count
                base_x = lay.time_col_w + day_index * lay.day_col_w + 2
                x0 = base_x + slot * slot_w
                x1 = x0 + slot_w - 2

                start_offset = (start - lay.start_hour * 60) / 60
                end_offset = (end - lay.start_hour * 60) / 60
                y0 = lay.header_h + start_offset * lay.row_h
                y1 = lay.header_h + end_offset * lay.row_h
                y0 = max(lay.header_h, min(y0, h))
                y1 = max(lay.header_h, min(y1, h))
                if y1 <= y0:
                    continue

                if use_compare_palette:
                    fill = self.compare_color_a if cls.get("_compare_source", 0) == 0 else self.compare_color_b
                else:
                    fill = cls.get("_color", "#b7d8ff") if is_comparison_schedule else ("#ff7b7b" if class_idx in conflicts else cls.get("_color", "#b7d8ff"))
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="black")
                label = (
                    f"{cls.get('class_name')}\n"
                    + ("" if use_compare_palette else f"{cls.get('section')}\n")
                    + f"{hhmm_to_ampm(meeting['start_time'])}-{hhmm_to_ampm(meeting['end_time'])}\n"
                    f"{location_or_na(meeting)}"
                )
                self.canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=label, font=("Arial", 8), width=max(20, slot_w - 6))

    def create_schedule(self):
        win = tk.Toplevel(self.root)
        win.title("Create Schedule")
        ttk.Label(win, text="Schedule name:").pack(padx=8, pady=8)
        entry = ttk.Entry(win, width=30)
        entry.pack(padx=8, pady=4)

        def submit():
            name = entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Name is required.")
                return
            if any(s.get("name") == name for s in self.data.get("schedules", [])):
                messagebox.showerror("Error", "A schedule with this name already exists.")
                return
            self.data["schedules"].append({"name": name, "classes": []})
            self.selected_schedule_name.set(name)
            self.refresh_schedule_dropdown()
            self.redraw_views()
            win.destroy()

        ttk.Button(win, text="Create", command=submit).pack(pady=8)
        win.grab_set()

    def delete_schedule(self):
        schedule = self.get_selected_schedule()
        if not schedule:
            return
        if len(self.data.get("schedules", [])) <= 1:
            messagebox.showerror("Error", "At least one schedule must remain.")
            return
        if not messagebox.askyesno("Confirm", f"Delete schedule '{schedule['name']}'?"):
            return

        self.data["schedules"] = [s for s in self.data["schedules"] if s.get("name") != schedule.get("name")]
        self.refresh_schedule_dropdown()
        self.redraw_views()

    def open_add_class_dialog(self):
        schedule = self.get_selected_schedule()
        if not schedule:
            messagebox.showerror("Error", "No schedule selected.")
            return

        def on_submit(class_data):
            schedule["classes"].append(class_data)
            self.redraw_views()

        AddClassDialog(self.root, on_submit)

    def combine_schedules(self):
        names = [s.get("name") for s in self.data.get("schedules", [])]
        if len(names) < 2:
            messagebox.showerror("Error", "Need at least two schedules to combine.")
            return

        win = tk.Toplevel(self.root)
        win.title("Combine Schedules")

        ttk.Label(win, text="First schedule:").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ttk.Label(win, text="Second schedule:").grid(row=1, column=0, padx=8, pady=6, sticky="w")

        first_var = tk.StringVar(value=names[0])
        second_var = tk.StringVar(value=names[1])
        first_combo = ttk.Combobox(win, values=names, textvariable=first_var, state="readonly")
        second_combo = ttk.Combobox(win, values=names, textvariable=second_var, state="readonly")
        first_combo.grid(row=0, column=1, padx=8, pady=6)
        second_combo.grid(row=1, column=1, padx=8, pady=6)

        ttk.Label(win, text="Combined name:").grid(row=2, column=0, padx=8, pady=6, sticky="w")
        name_entry = ttk.Entry(win)
        name_entry.insert(0, "Combined Schedule")
        name_entry.grid(row=2, column=1, padx=8, pady=6)

        def submit():
            n1, n2 = first_var.get(), second_var.get()
            if n1 == n2:
                messagebox.showerror("Error", "Choose two different schedules.")
                return
            new_name = name_entry.get().strip()
            if not new_name:
                messagebox.showerror("Error", "Combined name required.")
                return
            if any(s.get("name") == new_name for s in self.data.get("schedules", [])):
                messagebox.showerror("Error", "Schedule name already exists.")
                return

            s1 = next(s for s in self.data["schedules"] if s["name"] == n1)
            s2 = next(s for s in self.data["schedules"] if s["name"] == n2)

            merged_classes = []
            for c in s1.get("classes", []):
                cpy = copy.deepcopy(c)
                cpy["_color"] = cpy.get("_color", "#b7d8ff")
                merged_classes.append(cpy)
            for c in s2.get("classes", []):
                cpy = copy.deepcopy(c)
                cpy["_color"] = cpy.get("_color", "#ffd39b")
                merged_classes.append(cpy)

            combined = {
                "name": new_name,
                "source_schedules": [n1, n2],
                "classes": merged_classes,
            }
            self.data["schedules"].append(combined)
            self.selected_schedule_name.set(new_name)
            self.refresh_schedule_dropdown()
            self.redraw_views()
            win.destroy()

        ttk.Button(win, text="Combine", command=submit).grid(row=3, column=0, columnspan=2, pady=8)
        win.grab_set()

    def compare_schedules_window(self):
        win = tk.Toplevel(self.root)
        win.title("Compare Schedules")
        win.resizable(False, False)

        file1_var = tk.StringVar(value="")
        file2_var = tk.StringVar(value="")
        data1: dict = {"schedules": []}
        data2: dict = {"schedules": []}
        names1: list[str] = []
        names2: list[str] = []

        pair_rows: list[dict] = []
        pairs_container = ttk.Frame(win)

        def refresh_pair_labels():
            for i, pair in enumerate(pair_rows, start=1):
                pair["label"].configure(text=f"Pair {i}")

        def remove_pair_row(pair_ref: dict):
            if len(pair_rows) <= 1:
                messagebox.showinfo("Compare", "At least one pairing must remain active.")
                return
            pair_ref["frame"].destroy()
            pair_rows.remove(pair_ref)
            refresh_pair_labels()

        def add_pair_row(default_index: int | None = None):
            pair_no = len(pair_rows) + 1
            row = ttk.Frame(pairs_container)
            row.pack(fill="x", pady=3)
            label = ttk.Label(row, text=f"Pair {pair_no}")
            label.pack(side="left", padx=(0, 6))
            left_var = tk.StringVar(value="")
            right_var = tk.StringVar(value="")
            left_combo = ttk.Combobox(row, textvariable=left_var, state="readonly", width=24)
            right_combo = ttk.Combobox(row, textvariable=right_var, state="readonly", width=24)
            left_combo.pack(side="left", padx=4)
            ttk.Label(row, text="vs").pack(side="left")
            right_combo.pack(side="left", padx=4)
            pair_ref = {
                "frame": row,
                "label": label,
                "left": left_var,
                "right": right_var,
                "left_combo": left_combo,
                "right_combo": right_combo,
            }
            remove_btn = tk.Button(row, text="X", fg="red", width=2, command=lambda: remove_pair_row(pair_ref))
            remove_btn.pack(side="left", padx=(4, 0))
            pair_ref["remove_btn"] = remove_btn
            pair_rows.append(pair_ref)
            refresh_pair_labels()

            if names1:
                left_combo["values"] = names1
                left_var.set(names1[min(default_index or 0, len(names1) - 1)])
            if names2:
                right_combo["values"] = names2
                right_var.set(names2[min(default_index or 0, len(names2) - 1)])

        def pick_file(target: int):
            path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
            if not path:
                return
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = normalize_data_model(json.load(f))
                local_names = [s.get("name", "Untitled") for s in loaded.get("schedules", [])]
                if not local_names:
                    raise ValueError("No schedules found in file.")
                if target == 1:
                    file1_var.set(path)
                    data1["schedules"] = loaded["schedules"]
                    names1.clear()
                    names1.extend(local_names)
                    for i, pair in enumerate(pair_rows):
                        pair["left_combo"]["values"] = names1
                        pair["left"].set(names1[min(i, len(names1) - 1)])
                else:
                    file2_var.set(path)
                    data2["schedules"] = loaded["schedules"]
                    names2.clear()
                    names2.extend(local_names)
                    for i, pair in enumerate(pair_rows):
                        pair["right_combo"]["values"] = names2
                        pair["right"].set(names2[min(i, len(names2) - 1)])
            except Exception as exc:
                messagebox.showerror("Load Error", str(exc))

        ttk.Label(win, text="JSON File 1").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(win, textvariable=file1_var, width=48).grid(row=0, column=1, padx=8, pady=6)
        ttk.Button(win, text="Browse", command=lambda: pick_file(1)).grid(row=0, column=2, padx=8, pady=6)

        ttk.Label(win, text="JSON File 2").grid(row=1, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(win, textvariable=file2_var, width=48).grid(row=1, column=1, padx=8, pady=6)
        ttk.Button(win, text="Browse", command=lambda: pick_file(2)).grid(row=1, column=2, padx=8, pady=6)

        ttk.Label(win, text="Comparison Pairs (File1 schedule vs File2 schedule)").grid(row=2, column=0, columnspan=3, padx=8, pady=(12, 4), sticky="w")
        pairs_container.grid(row=3, column=0, columnspan=3, padx=8, pady=4, sticky="w")
        add_pair_row(default_index=0)
        add_pair_row(default_index=1)
        ttk.Button(win, text="Add Pair", command=lambda: add_pair_row(default_index=len(pair_rows))).grid(row=4, column=0, padx=8, pady=6, sticky="w")

        def make_comparison_schedule(left: dict, right: dict, name: str) -> dict:
            left_classes = copy.deepcopy(left.get("classes", []))
            right_classes = copy.deepcopy(right.get("classes", []))

            for c in left_classes:
                c["_compare_source"] = 0
                c["_color"] = "#a9f5a9" if any(class_items_overlap(c, r) for r in right_classes) else "#ff9e9e"
            for c in right_classes:
                c["_compare_source"] = 1
                c["_color"] = "#a9f5a9" if any(class_items_overlap(c, l) for l in left_classes) else "#ff9e9e"

            return {
                "name": name,
                "is_comparison_pair": True,
                "source_schedules": [left.get("name", "left"), right.get("name", "right")],
                "classes": left_classes + right_classes,
            }

        def submit():
            if not file1_var.get() or not file2_var.get():
                messagebox.showerror("Error", "Please select both JSON files.")
                return
            if not pair_rows or not all(p["left"].get() and p["right"].get() for p in pair_rows):
                messagebox.showerror("Error", "Please select schedules for all comparison pairs.")
                return

            get1 = {s.get("name"): s for s in data1.get("schedules", [])}
            get2 = {s.get("name"): s for s in data2.get("schedules", [])}

            created_names = []
            for pair_index, pair in enumerate(pair_rows, start=1):
                n1 = pair["left"].get()
                n2 = pair["right"].get()
                base_name = f"comparison_pair_{pair_index}"
                if n1 not in get1 or n2 not in get2:
                    messagebox.showerror("Error", f"Invalid selection: {n1} vs {n2}")
                    return
                new_name = base_name
                suffix = 2
                while any(s.get("name") == new_name for s in self.data.get("schedules", [])):
                    new_name = f"{base_name}_{suffix}"
                    suffix += 1
                self.data["schedules"].append(make_comparison_schedule(get1[n1], get2[n2], new_name))
                created_names.append(new_name)

            self.selected_schedule_name.set(created_names[0])
            self.refresh_schedule_dropdown()
            self.redraw_views()
            messagebox.showinfo("Compare", f"Created: {', '.join(created_names)}\nGreen = overlap, Red = no overlap")
            win.destroy()

        ttk.Button(win, text="Compare", command=submit).grid(row=5, column=0, columnspan=3, pady=12)
        win.grab_set()

    def smart_generate(self):
        base = self.get_selected_schedule()
        if not base:
            return

        grouped: dict[str, dict[str, list[dict]]] = {}
        for cls in base.get("classes", []):
            grouped.setdefault(cls["class_name"], {}).setdefault(cls["section"], []).append(cls)

        class_names = list(grouped.keys())
        if not class_names:
            messagebox.showinfo("Smart Generate", "No classes to generate from.")
            return

        combos = []

        def backtrack(i: int, current: list[dict]):
            if i == len(class_names):
                combos.append(copy.deepcopy(current))
                return
            cname = class_names[i]
            for section_bundle in grouped[cname].values():
                if any(class_items_overlap(option, existing) for option in section_bundle for existing in current):
                    continue
                current.extend(section_bundle)
                backtrack(i + 1, current)
                del current[-len(section_bundle):]

        backtrack(0, [])

        if not combos:
            messagebox.showinfo("Smart Generate", "No non-conflicting combinations found.")
            return

        created = 0
        for idx, combo in enumerate(combos, start=1):
            new_name = f"{base['name']}_generated_{idx}"
            while any(s.get("name") == new_name for s in self.data.get("schedules", [])):
                idx += 1
                new_name = f"{base['name']}_generated_{idx}"
            self.data["schedules"].append(
                {
                    "name": new_name,
                    "source_schedules": [base["name"]],
                    "classes": copy.deepcopy(combo),
                }
            )
            created += 1

        self.refresh_schedule_dropdown()
        messagebox.showinfo("Smart Generate", f"Created {created} schedule(s).")

    def merge_overlaps(self):
        base = self.get_selected_schedule()
        if not base:
            return

        classes = base.get("classes", [])
        if len(classes) < 2:
            messagebox.showinfo("Merge Overlaps", "Need at least two classes to detect overlaps.")
            return

        n = len(classes)
        adjacency = {i: set() for i in range(n)}
        for i in range(n):
            for j in range(i + 1, n):
                if class_items_overlap(classes[i], classes[j]):
                    adjacency[i].add(j)
                    adjacency[j].add(i)

        visited = set()
        merged_classes = []
        merged_groups = 0

        for i in range(n):
            if i in visited:
                continue
            stack = [i]
            comp = []
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                comp.append(cur)
                stack.extend(adjacency[cur] - visited)

            if len(comp) == 1:
                merged_classes.append(copy.deepcopy(classes[comp[0]]))
                continue

            group = [classes[idx] for idx in comp]
            all_days = []
            for c in group:
                for d in c.get("days", []):
                    if d in DAY_ORDER and d not in all_days:
                        all_days.append(d)
            all_days.sort(key=DAY_ORDER.index)

            start_min = min(time_to_minutes(c["start_time"]) for c in group)
            end_min = max(time_to_minutes(c["end_time"]) for c in group)
            merged_classes.append(
                {
                    "class_name": " + ".join(sorted({c.get("class_name", "").strip() for c in group if c.get("class_name")})),
                    "section": "MERGED",
                    "days": all_days,
                    "start_time": f"{start_min // 60:02d}:{start_min % 60:02d}",
                    "end_time": f"{end_min // 60:02d}:{end_min % 60:02d}",
                    "location": " / ".join(sorted({c.get("location", "").strip() for c in group if c.get("location")})) or "N/A",
                    "teacher": " / ".join(sorted({c.get("teacher", "").strip() for c in group if c.get("teacher")})),
                    "credits": sum(int(c.get("credits", 0)) for c in group),
                    "_color": "#c6f6c6",
                }
            )
            merged_groups += 1

        if merged_groups == 0:
            messagebox.showinfo("Merge Overlaps", "No overlapping classes found.")
            return

        new_name = f"{base['name']}_merged_overlaps"
        suffix = 2
        while any(s.get("name") == new_name for s in self.data.get("schedules", [])):
            new_name = f"{base['name']}_merged_overlaps_{suffix}"
            suffix += 1

        self.data["schedules"].append(
            {
                "name": new_name,
                "source_schedules": [base["name"]],
                "classes": merged_classes,
            }
        )
        self.selected_schedule_name.set(new_name)
        self.refresh_schedule_dropdown()
        self.redraw_views()
        messagebox.showinfo("Merge Overlaps", f"Created '{new_name}' with {merged_groups} merged overlap group(s).")

    def save_json(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        messagebox.showinfo("Saved", f"Saved schedules to:\n{path}")

    def load_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.data = normalize_data_model(loaded)
            self.refresh_schedule_dropdown()
            self.redraw_views()
            messagebox.showinfo("Loaded", f"Loaded schedules from:\n{path}")
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))

    def export_pdf(self):
        schedule = self.get_selected_schedule()
        if not schedule:
            messagebox.showerror("Error", "No schedule selected.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not path:
            return

        page_w, page_h = landscape(letter)
        c = pdf_canvas.Canvas(path, pagesize=(page_w, page_h))

        margin = 30
        title_y = page_h - margin
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(page_w / 2, title_y, f"Schedule: {schedule.get('name', 'Untitled')}")

        grid_top = title_y - 25
        grid_bottom = margin
        grid_left = margin
        grid_right = page_w - margin

        total_w = grid_right - grid_left
        total_h = grid_top - grid_bottom

        lay = self.layout
        time_col_w = total_w * (lay.time_col_w / (lay.time_col_w + lay.day_col_w * 5))
        day_col_w = (total_w - time_col_w) / 5
        header_h = total_h * (lay.header_h / (lay.header_h + (lay.end_hour - lay.start_hour) * lay.row_h))
        body_h = total_h - header_h

        c.setLineWidth(1)
        c.rect(grid_left, grid_bottom, total_w, total_h)

        for i in range(6):
            if i == 0:
                x0 = grid_left
                x1 = grid_left + time_col_w
            else:
                x0 = grid_left + time_col_w + (i - 1) * day_col_w
                x1 = x0 + day_col_w
            c.setFillColor(colors.lightgrey)
            c.rect(x0, grid_top - header_h, x1 - x0, header_h, fill=1, stroke=1)

            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 10)
            label = ["Time", "M", "T", "W", "Th", "F"][i]
            c.drawCentredString((x0 + x1) / 2, grid_top - header_h / 2 - 4, label)

        c.setStrokeColor(colors.lightgrey)
        for hr in range(lay.start_hour, lay.end_hour + 1):
            offset = (hr - lay.start_hour) / (lay.end_hour - lay.start_hour)
            y = grid_top - header_h - offset * body_h
            c.line(grid_left, y, grid_right, y)
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 8)
            c.drawRightString(grid_left + time_col_w - 3, y - 2, minutes_to_ampm(hr * 60))

        for i in range(6):
            x = grid_left + time_col_w + i * day_col_w
            if i == 5:
                continue
            c.line(x, grid_bottom, x, grid_top)

        classes = schedule.get("classes", [])
        conflicts = find_conflicting_indices(classes)
        is_comparison_schedule = self.is_comparison_pair_schedule(schedule)
        use_compare_palette = is_comparison_schedule and self.compare_alt_mode.get()
        day_to_idx = {d: i for i, d in enumerate(DAY_ORDER)}

        expanded_blocks = []
        for class_idx, cls in enumerate(classes):
            for meeting in expand_class_meetings(cls):
                block = dict(meeting)
                block["_class_idx"] = class_idx
                block["_class_ref"] = cls
                expanded_blocks.append(block)

        day_layouts = {day: compute_day_side_by_side_layout(expanded_blocks, day) for day in DAY_ORDER}

        for block_idx, meeting in enumerate(expanded_blocks):
            cls = meeting["_class_ref"]
            class_idx = meeting["_class_idx"]
            start = time_to_minutes(meeting["start_time"])
            end = time_to_minutes(meeting["end_time"])
            for d in meeting.get("days", []):
                if d not in day_to_idx:
                    continue
                d_idx = day_to_idx[d]
                placements, cluster_widths = day_layouts[d]
                slot, cluster = placements.get(block_idx, (0, 0))
                slot_count = max(cluster_widths.get(cluster, 1), 1)
                usable_w = day_col_w - 4
                slot_w = usable_w / slot_count
                base_x = grid_left + time_col_w + d_idx * day_col_w + 2
                x0 = base_x + slot * slot_w
                x1 = x0 + slot_w - 2

                y0 = grid_top - header_h - ((start - lay.start_hour * 60) / ((lay.end_hour - lay.start_hour) * 60)) * body_h
                y1 = grid_top - header_h - ((end - lay.start_hour * 60) / ((lay.end_hour - lay.start_hour) * 60)) * body_h
                body_top = grid_top - header_h
                body_bottom = grid_bottom
                y0 = max(body_bottom, min(y0, body_top))
                y1 = max(body_bottom, min(y1, body_top))
                if y0 <= y1:
                    continue

                if use_compare_palette:
                    color_hex = self.compare_color_a if cls.get("_compare_source", 0) == 0 else self.compare_color_b
                else:
                    color_hex = cls.get("_color", "#b7d8ff") if is_comparison_schedule else ("#ff7b7b" if class_idx in conflicts else cls.get("_color", "#b7d8ff"))
                try:
                    fill = colors.HexColor(color_hex)
                except Exception:
                    fill = colors.HexColor("#b7d8ff")

                c.setFillColor(fill)
                c.setStrokeColor(colors.black)
                c.rect(x0, y1, x1 - x0, y0 - y1, fill=1, stroke=1)

                c.setFillColor(colors.black)
                c.setFont("Helvetica", 7)
                text = (
                    f"{cls.get('class_name')}" + ("" if use_compare_palette else f" ({cls.get('section')})") + "\n"
                    f"{hhmm_to_ampm(meeting['start_time'])}-{hhmm_to_ampm(meeting['end_time'])}\n"
                    f"{location_or_na(meeting)}"
                )
                tx = c.beginText(x0 + 3, y0 - 10)
                tx.setFont("Helvetica", 7)
                for line in text.split("\n"):
                    tx.textLine(line)
                c.drawText(tx)

        c.save()
        messagebox.showinfo("Exported", f"PDF exported to:\n{path}")


def main():
    root = tk.Tk()
    app = SchedulePlannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
