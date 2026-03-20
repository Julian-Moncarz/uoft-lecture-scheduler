#!/usr/bin/env python3
"""
Fetch lecture section times, rooms, and instructors from UofT timetable API.

Usage:
    python fetch_sections.py CSC110Y1 MAT137Y1 STA257H1
    python fetch_sections.py --from-solver   # auto-fetch courses from solve_ilp output
"""

import sys
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "https://api.easi.utoronto.ca/ttb/getCoursesByCodeAndSectionCode"
# Winter 2026 and full-year 2025-2026
SESSIONS_OF_INTEREST = {"20261", "20259-20261"}
DAYS = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}


def ms_to_time(ms: int) -> str:
    h, rem = divmod(ms, 3_600_000)
    m = rem // 60_000
    return f"{h:02d}:{m:02d}"


def fetch_course(code: str) -> dict:
    url = f"{API}/{code}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def parse_sections(code: str, data: dict) -> list[dict]:
    rows = []
    courses = data.get("payload", {}).get("pageableCourse", {}).get("courses", [])
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
            instructors = ", ".join(
                f"{i.get('firstName', '')} {i.get('lastName', '')}".strip()
                for i in sec.get("instructors", [])
            ) or "TBA"
            for mt in sec.get("meetingTimes", []):
                day = DAYS.get(mt["start"]["day"], "?")
                start = ms_to_time(mt["start"]["millisofday"])
                end = ms_to_time(mt["end"]["millisofday"])
                bld = mt.get("building") or {}
                room = f"{bld.get('buildingCode', '?')} {bld.get('buildingRoomNumber', '?')}"
                rows.append({
                    "course": code,
                    "section": sec["name"],
                    "term": section_code,
                    "day": day,
                    "time": f"{start}-{end}",
                    "room": room.strip(),
                    "instructor": instructors,
                    "enrolment": f"{sec.get('currentEnrolment', '?')}/{sec.get('maxEnrolment', '?')}",
                })
    return rows


def get_solver_courses() -> list[str]:
    """Extract unique courses from section_cache.json that have >0 sections."""
    with open("section_cache.json") as f:
        cache = json.load(f)
    # Just return all courses with sections > 0
    return [c for c, s in cache.items() if s > 0]


def main():
    if "--from-solver" in sys.argv:
        courses = get_solver_courses()
        print(f"Fetching {len(courses)} courses from section_cache.json...\n")
    elif len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    else:
        courses = [a for a in sys.argv[1:] if not a.startswith("-")]

    all_rows = []
    errors = []

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_course, c): c for c in courses}
        for fut in as_completed(futures):
            code = futures[fut]
            try:
                data = fut.result()
                rows = parse_sections(code, data)
                all_rows.extend(rows)
            except Exception as e:
                errors.append(f"{code}: {e}")

    # Sort by day order then time
    day_order = {"Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6, "Sun": 7}
    all_rows.sort(key=lambda r: (r["course"], day_order.get(r["day"], 9), r["time"]))

    # Print table
    if all_rows:
        header = f"{'Course':<12} {'Section':<10} {'Term':<4} {'Day':<4} {'Time':<12} {'Room':<12} {'Instructor':<30} {'Enrol'}"
        print(header)
        print("-" * len(header))
        for r in all_rows:
            print(f"{r['course']:<12} {r['section']:<10} {r['term']:<4} {r['day']:<4} {r['time']:<12} {r['room']:<12} {r['instructor']:<30} {r['enrolment']}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  {e}")

    print(f"\n{len(all_rows)} lecture meetings across {len(courses)} courses")

    # Also save as JSON for downstream use
    with open("sections_timetable.json", "w") as f:
        json.dump(all_rows, f, indent=2)
    print("Saved to sections_timetable.json")


if __name__ == "__main__":
    main()
