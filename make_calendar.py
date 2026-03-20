#!/usr/bin/env python3
"""
Generate an .ics calendar file with all lecture sections of the optimal courses,
mapped to a specific target week.

Usage:
    python make_calendar.py                    # defaults to next Mon-Fri
    python make_calendar.py 2026-03-16         # specify the Monday of the target week
    python make_calendar.py 2026-03-16 3       # 3 weeks starting from that Monday
"""

import sys
import json
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# --- Config ---
API = "https://api.easi.utoronto.ca/ttb/getCoursesByCodeAndSectionCode"
SESSIONS_OF_INTEREST = {"20261", "20259-20261"}
DAYS = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}

# Optimal courses from solver (extracted from solve_ilp output)
OPTIMAL_COURSES = [
    "COG402H1", "COG403H1", "COG498H1", "COG499H1",
    "CSC111H1", "CSC148H1", "CSC240H1", "CSC369H1",
    "ECO101H1", "ECO208Y1", "ECO325H1",
    "ESC190H1", "ESC204H1",
    "MAT188H1", "MAT247H1", "MAT267H1", "MAT334H1", "MAT351Y1", "MAT477H1",
    "PHY131H1", "PHY254H1",
    "PSY270H1", "PSY290H1",
    "STA130H1", "STA261H1", "STA302H1",
    # Engineering
    "ECE295H1", "ECE297H1", "ECE302H1", "ECE311H1",
    "MIE240H1", "MIE350H1",
]

# Which programs each course covers (for event descriptions)
COURSE_COVERS = {
    "COG402H1": ["COGSCI-Y4"], "COG403H1": ["COGSCI-Y4"],
    "COG498H1": ["COGSCI-Y4"], "COG499H1": ["COGSCI-Y4"],
    "CSC111H1": ["CS-Y1", "DS-Y1", "COGSCI-Y1"],
    "CSC148H1": ["COGSCI-Y1"], "CSC240H1": ["CS-Y2", "DS-Y2"],
    "CSC369H1": ["CS-Y3"],
    "ECO101H1": ["ECON-Y1"], "ECO208Y1": ["ECON-Y2"], "ECO325H1": ["ECON-Y3"],
    "ESC190H1": ["ENGSCI-Y1"], "ESC204H1": ["ENGSCI-Y2"],
    "MAT247H1": ["MATH-Y1"], "MAT267H1": ["MATH-Y2"],
    "MAT334H1": ["PHYS-Y3"], "MAT351Y1": ["MATH-Y3"], "MAT477H1": ["MATH-Y4"],
    "PHY131H1": ["PHYS-Y1"], "PHY254H1": ["PHYS-Y2"],
    "PSY270H1": ["COGSCI-Y2"], "PSY290H1": ["COGSCI-Y3"],
    "STA130H1": ["STAT-Y1"], "STA261H1": ["STAT-Y2"],
    "STA302H1": ["STAT-Y3", "DS-Y3"],
    "MAT188H1": ["ENG-Y1"],
    "ECE295H1": ["ECE-Y2"], "ECE297H1": ["ECE-Y2"],
    "ECE302H1": ["ECE-Y3"], "ECE311H1": ["ECE-Y3"],
    "MIE240H1": ["INDE-Y2"],
    "MIE350H1": ["INDE-Y3"],
}


def fetch_course(code: str) -> dict:
    url = f"{API}/{code}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def ms_to_hm(ms: int) -> tuple[int, int]:
    h, rem = divmod(ms, 3_600_000)
    m = rem // 60_000
    return h, m


def ics_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def escape_ics(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def build_events(course_data: dict, code: str, monday: datetime) -> list[str]:
    """Build ICS VEVENT blocks for all lecture sections of a course, mapped to the target week."""
    events = []
    courses = course_data.get("payload", {}).get("pageableCourse", {}).get("courses", [])

    for course in courses:
        section_code = course.get("sectionCode", "")
        sessions = set(course.get("sessions", []))
        if not sessions & SESSIONS_OF_INTEREST:
            continue

        for sec in course.get("sections", []):
            if sec.get("teachMethod") != "LEC":
                continue
            if sec.get("cancelInd") == "Y":
                continue

            sec_name = sec["name"]
            instructors = ", ".join(
                f"{i.get('firstName', '')} {i.get('lastName', '')}".strip()
                for i in sec.get("instructors", [])
            ) or "TBA"
            enrolment = f"{sec.get('currentEnrolment', '?')}/{sec.get('maxEnrolment', '?')}"
            covers = ", ".join(COURSE_COVERS.get(code, []))

            for mt in sec.get("meetingTimes", []):
                day_num = mt["start"]["day"]  # 1=Mon
                if day_num > 5:
                    continue  # skip weekends

                start_h, start_m = ms_to_hm(mt["start"]["millisofday"])
                end_h, end_m = ms_to_hm(mt["end"]["millisofday"])

                # Map to target week
                event_date = monday + timedelta(days=day_num - 1)
                dt_start = event_date.replace(hour=start_h, minute=start_m, second=0)
                dt_end = event_date.replace(hour=end_h, minute=end_m, second=0)

                bld = mt.get("building") or {}
                room = f"{bld.get('buildingCode', '?')} {bld.get('buildingRoomNumber', '')}".strip()

                summary = f"{code} {sec_name} — {instructors}"
                description = (
                    f"Course: {code} ({section_code})\\n"
                    f"Section: {sec_name}\\n"
                    f"Instructor: {instructors}\\n"
                    f"Enrolment: {enrolment}\\n"
                    f"Covers programs: {covers}\\n"
                    f"Room: {room}"
                )

                uid = str(uuid.uuid4())
                event = (
                    "BEGIN:VEVENT\r\n"
                    f"UID:{uid}\r\n"
                    f"DTSTART:{ics_dt(dt_start)}\r\n"
                    f"DTEND:{ics_dt(dt_end)}\r\n"
                    f"SUMMARY:{escape_ics(summary)}\r\n"
                    f"LOCATION:{escape_ics(room)}\r\n"
                    f"DESCRIPTION:{description}\r\n"
                    "END:VEVENT\r\n"
                )
                events.append(event)

    return events


def main():
    # Determine target Monday(s)
    # Usage: make_calendar.py [START_MONDAY] [NUM_WEEKS]
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        monday = datetime.strptime(sys.argv[1], "%Y-%m-%d")
    else:
        today = datetime.now()
        days_ahead = (7 - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        monday = today.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)

    num_weeks = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    mondays = [monday + timedelta(weeks=w) for w in range(num_weeks)]

    last_friday = mondays[-1] + timedelta(days=4)
    print(f"Target: {monday.strftime('%a %b %d')} – {last_friday.strftime('%a %b %d, %Y')} ({num_weeks} week{'s' if num_weeks > 1 else ''})")
    print(f"Fetching {len(OPTIMAL_COURSES)} courses from UofT API...\n")

    # Fetch all courses in parallel (one fetch, reuse for all weeks)
    all_events = []
    errors = []
    course_data = {}

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_course, c): c for c in OPTIMAL_COURSES}
        for fut in as_completed(futures):
            code = futures[fut]
            try:
                course_data[code] = fut.result()
            except Exception as e:
                errors.append(f"{code}: {e}")
                print(f"  {code}: ERROR — {e}")

    for week_monday in mondays:
        week_label = week_monday.strftime('%b %d')
        week_events = []
        for code, data in course_data.items():
            events = build_events(data, code, week_monday)
            week_events.extend(events)
        all_events.extend(week_events)
        print(f"  Week of {week_label}: {len(week_events)} events")

    if errors:
        print(f"\n{len(errors)} errors encountered")

    # Build .ics file
    cal = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//TAISI//Lecture Visit Scheduler//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        "X-WR-CALNAME:UofT Lecture Visits\r\n"
    )
    for event in all_events:
        cal += event
    cal += "END:VCALENDAR\r\n"

    out_path = "lecture_visits.ics"
    with open(out_path, "w") as f:
        f.write(cal)

    print(f"\n{len(all_events)} events written to {out_path}")
    print("Open this file to import into Apple Calendar, Google Calendar, or Outlook.")


if __name__ == "__main__":
    main()
