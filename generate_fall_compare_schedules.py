"""Generate fall comparison schedules from a local combined_schedules.json file.

Usage:
    python generate_fall_compare_schedules.py
    python generate_fall_compare_schedules.py --schedule "Fall 2026"

The source combined_schedules.json file is intentionally user-managed and is not
committed here. This script copies every class from the selected fall schedule
and then creates one output schedule for each requested PEM1121/PEM1148 option,
with PEM1131 included in every generated schedule.
"""

import argparse
import copy
import json
from pathlib import Path

PEM1131 = {
    "class_name": "PEM1131",
    "section": "0003",
    "days": ["M", "W"],
    "start_time": "10:40",
    "end_time": "11:30",
    "location": "TUL B014",
    "teacher": "Kristopher White",
    "credits": 1,
    "_color": "#77DD77",
    "meetings": [
        {
            "days": ["M", "W"],
            "start_time": "10:40",
            "end_time": "11:30",
            "location": "TUL B014",
        }
    ],
}

FALL_OPTIONS = [
    {
        "class_name": "PEM1121",
        "section": "0008",
        "days": ["M", "W"],
        "start_time": "16:50",
        "end_time": "17:40",
        "location": "TUL B005",
        "teacher": "Kristopher White",
        "credits": 1,
        "_color": "#B19CD9",
        "meetings": [{"days": ["M", "W"], "start_time": "16:50", "end_time": "17:40", "location": "TUL B005"}],
    },
    {
        "class_name": "PEM1121",
        "section": "0009",
        "days": ["M", "W"],
        "start_time": "16:50",
        "end_time": "17:40",
        "location": "TUL B016",
        "teacher": "Kristopher White",
        "credits": 1,
        "_color": "#B19CD9",
        "meetings": [{"days": ["M", "W"], "start_time": "16:50", "end_time": "17:40", "location": "TUL B016"}],
    },
    {
        "class_name": "PEM1148",
        "section": "0001",
        "days": ["M", "W"],
        "start_time": "10:40",
        "end_time": "11:30",
        "location": "TUL 2018",
        "teacher": "Kristopher White",
        "credits": 1,
        "_color": "#B19CD9",
        "meetings": [{"days": ["M", "W"], "start_time": "10:40", "end_time": "11:30", "location": "TUL 2018"}],
    },
    {
        "class_name": "PEM1148",
        "section": "0002",
        "days": ["M", "W"],
        "start_time": "12:00",
        "end_time": "12:50",
        "location": "TUL 2012",
        "teacher": "Kristopher White",
        "credits": 1,
        "_color": "#B19CD9",
        "meetings": [{"days": ["M", "W"], "start_time": "12:00", "end_time": "12:50", "location": "TUL 2012"}],
    },
]


def class_key(class_item):
    meetings = class_item.get("meetings") or [
        {
            "days": class_item.get("days", []),
            "start_time": class_item.get("start_time", ""),
            "end_time": class_item.get("end_time", ""),
            "location": class_item.get("location", ""),
        }
    ]
    meeting_key = tuple(
        sorted(
            (
                tuple(m.get("days", [])),
                m.get("start_time", ""),
                m.get("end_time", ""),
                m.get("location", ""),
            )
            for m in meetings
        )
    )
    return class_item.get("class_name", ""), class_item.get("section", ""), meeting_key


def dedup_classes(classes):
    seen = set()
    result = []
    for item in classes:
        key = class_key(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def load_fall_schedule(source_path, schedule_name):
    data = json.loads(source_path.read_text(encoding="utf-8"))
    schedules = data.get("schedules", [])
    if not schedules:
        raise ValueError(f"No schedules found in {source_path}")

    if schedule_name:
        for schedule in schedules:
            if schedule.get("name") == schedule_name:
                return schedule
        raise ValueError(f"Schedule named {schedule_name!r} not found in {source_path}")

    for schedule in schedules:
        if "fall" in schedule.get("name", "").lower():
            return schedule
    return schedules[0]


def build_schedules(fall_schedule):
    base_classes = copy.deepcopy(fall_schedule.get("classes", []))
    schedules = []
    for option in FALL_OPTIONS:
        classes = dedup_classes(base_classes + [copy.deepcopy(PEM1131), copy.deepcopy(option)])
        schedules.append(
            {
                "name": f"Fall Compare - {option['class_name']} {option['section']} + PEM1131 0003",
                "source_schedules": [fall_schedule.get("name", "Fall Schedule")],
                "classes": classes,
            }
        )
    return {"schedules": schedules}


def main():
    parser = argparse.ArgumentParser(description="Generate fall_compare_schedules.json from combined_schedules.json fall schedule.")
    parser.add_argument("--source", default="combined_schedules.json", help="Input combined schedules JSON path.")
    parser.add_argument("--schedule", default="", help="Exact fall schedule name to copy from source. Defaults to first schedule containing 'fall', or first schedule.")
    parser.add_argument("--output", default="fall_compare_schedules.json", help="Output JSON path.")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        raise SystemExit(f"Missing {source_path}. Add your combined_schedules.json file, then rerun this generator.")

    fall_schedule = load_fall_schedule(source_path, args.schedule)
    output = build_schedules(fall_schedule)
    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {args.output} using base schedule {fall_schedule.get('name', 'Fall Schedule')!r}")


if __name__ == "__main__":
    main()
