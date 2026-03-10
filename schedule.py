#!/usr/bin/env python3
"""
Configurable lecture visit scheduler.

Takes the optimal set cover solution and assigns sections to people
based on their availability, maximizing cohort-weighted coverage.

All configuration is in CONFIG below — edit freely.
"""

import json
import time
import urllib.request
from datetime import datetime, timedelta

# ══════════════════════════════════════════════════════════════════════
# CONFIGURATION — edit this section
# ══════════════════════════════════════════════════════════════════════

CONFIG = {
    # Time period: list of dates to schedule over.
    # Each date is a scheduling day. Sections are matched by day-of-week.
    # Use "week:YYYY-MM-DD" to expand to Mon-Fri of that week.
    "dates": ["week:2026-03-09"],  # Week of Mar 9, 2026 (current week)

    # People and their availability.
    # Each person has per-day-of-week windows and max visits per day.
    # Day names: mon, tue, wed, thu, fri, sat, sun
    # Windows: list of [start_hour, end_hour] in 24h format
    # max_per_day: max lectures that person will attend on that day
    "people": {
        "Julian": {
            "tue": {"windows": [[10, 15], [16, 19]], "max": 1},
            "wed": {"windows": [[10, 21]], "max": 1},
            "thu": {"windows": [[10, 21]], "max": 1},
            "fri": {"windows": [[11, 16]], "max": 1},
        },
        "Joseph": {
            "mon": {"windows": [[10, 15]], "max": 1},
            "tue": {"windows": [[13, 15], [17, 18]], "max": 1},
            "wed": {"windows": [[10, 16], [17, 21]], "max": 1},
            "thu": {"windows": [[10, 12]], "max": 1},
            "fri": {"windows": [[10, 15]], "max": 1},
        },
    },

    # Sections already visited (course_code:section_name, e.g. "CSC209H1:LEC0101")
    # These are excluded from scheduling.
    "already_visited": [],

    # Cohort sizes per program-year (used for prioritization)
    "cohorts": {
        "CS-Y1": 381, "CS-Y2": 675, "CS-Y3": 497,
        "MATH-Y1": 193, "MATH-Y2": 131, "MATH-Y3": 84, "MATH-Y4": 32,
        "STAT-Y1": 344, "STAT-Y2": 287, "STAT-Y3": 99,
        "DS-Y1": 54, "DS-Y2": 45, "DS-Y3": 35,
        "PHYS-Y1": 418, "PHYS-Y2": 348, "PHYS-Y3": 153,
        "ENGSCI-Y1": 253, "ENGSCI-Y2": 208,
        "COGSCI-Y1": 287, "COGSCI-Y2": 239, "COGSCI-Y3": 191,
        "ECON-Y1": 248, "ECON-Y2": 207, "ECON-Y3": 110,
    },

    # Optimal set cover solution (Winter 2026): course -> program-years covered
    "cover_solution": {
        "MAT137Y1": ["CS-Y1", "STAT-Y1", "DS-Y1", "PHYS-Y1", "COGSCI-Y1", "ECON-Y1"],
        "MAT157Y1": ["CS-Y1", "MATH-Y1", "STAT-Y1", "DS-Y1", "PHYS-Y1", "COGSCI-Y1", "ECON-Y1"],
        "STA255H1": ["CS-Y2"],
        "CSC369H1": ["CS-Y3"],
        "MAT267H1": ["MATH-Y2"],
        "MAT351Y1": ["MATH-Y3"],
        "STA261H1": ["STAT-Y2", "DS-Y2"],
        "STA302H1": ["STAT-Y3", "DS-Y3"],
        "PHY224H1": ["PHYS-Y2"],
        "MAT334H1": ["PHYS-Y3"],
        "ESC190H1": ["ENGSCI-Y1"],
        "BME205H1": ["ENGSCI-Y2"],
        "PSY270H1": ["COGSCI-Y2"],
        "PHL342H1": ["COGSCI-Y3"],
        "ECO206Y1": ["ECON-Y2"],
        "ECO325H1": ["ECON-Y3"],
    },
}

# ══════════════════════════════════════════════════════════════════════
# END CONFIGURATION
# ══════════════════════════════════════════════════════════════════════

API_BASE = "https://api.easi.utoronto.ca/ttb/getCoursesByCodeAndSectionCode"
DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NUM_TO_NAME = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}


def expand_dates(date_specs: list[str]) -> list[datetime]:
    """Expand date specs into concrete dates."""
    dates = []
    for spec in date_specs:
        if spec.startswith("week:"):
            # Find Monday of that week
            d = datetime.strptime(spec[5:], "%Y-%m-%d")
            monday = d - timedelta(days=d.weekday())
            for i in range(5):  # Mon-Fri
                dates.append(monday + timedelta(days=i))
        else:
            dates.append(datetime.strptime(spec, "%Y-%m-%d"))
    return sorted(set(dates))


def fetch_sections(code: str) -> list[dict]:
    """Fetch eligible lecture sections for a course from UofT API."""
    url = f"{API_BASE}/{code}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  ERROR fetching {code}: {e}")
        return []

    results = []
    courses = data.get("payload", {}).get("pageableCourse", {}).get("courses", [])
    for course in courses:
        if course.get("campus") != "St. George":
            continue
        # Only Winter 2026 session
        if "20261" not in course.get("sessions", []):
            continue
        for section in course.get("sections", []):
            if section.get("teachMethod") != "LEC":
                continue
            if section.get("cancelInd") == "Y":
                continue
            modes = [dm.get("mode") for dm in section.get("deliveryModes", [])]
            if "INPER" not in modes:
                continue

            meeting_times = section.get("meetingTimes", [])
            # Skip sections with any 9am start
            has_9am = any(
                mt.get("start", {}).get("millisofday") == 32400000
                for mt in meeting_times
            )
            if has_9am:
                continue

            # Extract ALL meeting times — each is a day we could attend
            # Deduplicate by (day, start, end) since year-long courses list
            # meetings for both Fall and Winter sessions
            meetings = []
            seen_meetings = set()
            for mt in meeting_times:
                day_num = mt.get("start", {}).get("day")
                start_ms = mt.get("start", {}).get("millisofday", 0)
                end_ms = mt.get("end", {}).get("millisofday", 0)
                dedup_key = (day_num, start_ms, end_ms)
                if dedup_key in seen_meetings:
                    continue
                seen_meetings.add(dedup_key)
                start_hour = start_ms / 3_600_000
                end_hour = end_ms / 3_600_000
                building = mt.get("building", {})
                room = f"{building.get('buildingCode', '??')}{building.get('buildingRoomNumber', '??')}"
                meetings.append({
                    "day_num": day_num,
                    "day_name": DAY_NUM_TO_NAME.get(day_num, "?"),
                    "start_hour": start_hour,
                    "end_hour": end_hour,
                    "start_time": f"{int(start_hour)}:{int((start_hour % 1) * 60):02d}",
                    "end_time": f"{int(end_hour)}:{int((end_hour % 1) * 60):02d}",
                    "room": room,
                })

            results.append({
                "course": code,
                "section": section["name"],
                "section_id": f"{code}:{section['name']}",
                "meetings": meetings,  # ALL weekly meeting times
                "enrolment": section.get("currentEnrolment", 0),
                "max_enrolment": section.get("maxEnrolment", 0),
            })
    return results


def section_fits_window(section: dict, windows: list[list[int]]) -> bool:
    """Check if a section's time falls entirely within any availability window."""
    for win_start, win_end in windows:
        if section["start_hour"] >= win_start and section["end_hour"] <= win_end:
            return True
    return False


def solve():
    config = CONFIG
    dates = expand_dates(config["dates"])
    people = config["people"]
    cohorts = config["cohorts"]
    cover = config["cover_solution"]
    already_visited = set(config["already_visited"])

    print(f"Scheduling period: {dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")
    print(f"  {len(dates)} days: {', '.join(d.strftime('%a %b %d') for d in dates)}")
    print(f"People: {', '.join(people.keys())}")
    print(f"Courses to visit: {len(cover)}")
    print(f"Already visited: {len(already_visited)} sections")

    # Step 1: Fetch all section data
    print("\n=== FETCHING SECTION DATA ===\n")
    all_sections: list[dict] = []
    for code in sorted(cover.keys()):
        print(f"  {code}...", end=" ", flush=True)
        secs = fetch_sections(code)
        # Filter out already visited
        secs = [s for s in secs if s["section_id"] not in already_visited]
        all_sections.extend(secs)
        days_info = []
        for s in secs:
            meeting_days = [m["day_name"] for m in s["meetings"]]
            days_info.append(f"{s['section']}({'/'.join(meeting_days)})")
        print(f"{len(secs)} sections: {', '.join(days_info)}")
        time.sleep(0.1)

    print(f"\nTotal sections to schedule: {len(all_sections)}")

    # Step 2: Compute cohort weight for each course
    course_weight: dict[str, int] = {}
    for code, pys in cover.items():
        course_weight[code] = sum(cohorts.get(py, 0) for py in pys)

    # Step 3: For each section+meeting, determine which (person, date) pairs can attend
    # A "visit option" = (section_id, meeting_index, person, date)
    # Each person-date slot has a max capacity

    # Build slot capacities
    slot_capacity: dict[tuple[str, str], int] = {}  # (person, date_str) -> max
    for person_name, avail in people.items():
        for date in dates:
            day_name = DAY_NAMES[date.weekday()]
            if day_name in avail:
                date_str = date.strftime("%Y-%m-%d")
                slot_capacity[(person_name, date_str)] = avail[day_name]["max"]

    # For each section, find all compatible (meeting_index, person, date) combos
    # section_options[section_id] = list of (meeting_idx, person, date_str)
    section_options: dict[str, list[tuple[int, str, str]]] = {}
    for sec in all_sections:
        sid = sec["section_id"]
        options = []
        for mi, meeting in enumerate(sec["meetings"]):
            for person_name, avail in people.items():
                day_name = meeting["day_name"]
                if day_name not in avail:
                    continue
                if not section_fits_window(meeting, avail[day_name]["windows"]):
                    continue
                for date in dates:
                    if DAY_NAMES[date.weekday()] == day_name:
                        options.append((mi, person_name, date.strftime("%Y-%m-%d")))
        section_options[sid] = options

    # Step 4: Solve assignment via ILP
    # Each section needs exactly 1 visit (at any of its meeting times).
    # Maximize cohort-weighted assignments.

    from pulp import (LpMaximize, LpProblem, LpVariable, lpSum, LpBinary,
                      value, LpStatus, PULP_CBC_CMD)

    prob = LpProblem("LectureScheduler", LpMaximize)

    # Variables: assign[section_id][(mi, person, date)] = binary
    assign = {}
    for sec in all_sections:
        sid = sec["section_id"]
        assign[sid] = {}
        for opt in section_options.get(sid, []):
            mi, person, date_str = opt
            key = (sid, mi, person, date_str)
            vname = f"a_{sid}_{mi}_{person}_{date_str}".replace(":", "_")
            assign[sid][key] = LpVariable(vname, cat=LpBinary)

    # Objective: maximize cohort-weighted assignments
    prob += lpSum(
        course_weight.get(sec["course"], 0) * var
        for sec in all_sections
        for var in assign[sec["section_id"]].values()
    )

    # Constraint: each section assigned at most once (pick one meeting day)
    for sec in all_sections:
        sid = sec["section_id"]
        if assign[sid]:
            prob += lpSum(assign[sid].values()) <= 1

    # Constraint: slot capacity (per person per date)
    for (person, date_str), cap in slot_capacity.items():
        relevant = []
        for sec in all_sections:
            sid = sec["section_id"]
            for key, var in assign[sid].items():
                _, _, p, d = key
                if p == person and d == date_str:
                    relevant.append(var)
        if relevant:
            prob += lpSum(relevant) <= cap

    # Constraint: no time overlaps for the same person on the same date
    # Two meetings overlap if their time ranges intersect
    # Group variables by (person, date), then check all pairs
    from collections import defaultdict
    person_date_vars: dict[tuple[str, str], list[tuple[dict, int, any]]] = defaultdict(list)
    for sec in all_sections:
        sid = sec["section_id"]
        for key, var in assign[sid].items():
            _, mi, person, date_str = key
            meeting = sec["meetings"][mi]
            person_date_vars[(person, date_str)].append((meeting, mi, var))

    for (person, date_str), entries in person_date_vars.items():
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                m1, _, v1 = entries[i]
                m2, _, v2 = entries[j]
                # Check if they overlap (on the same day-of-week is implied by same date)
                if m1["start_hour"] < m2["end_hour"] and m2["start_hour"] < m1["end_hour"]:
                    prob += v1 + v2 <= 1

    # Solve
    solver = PULP_CBC_CMD(msg=0)
    prob.solve(solver)

    print(f"\nSolver status: {LpStatus[prob.status]}")

    # Extract solution
    assignments: list[dict] = []
    for sec in all_sections:
        sid = sec["section_id"]
        for key, var in assign[sid].items():
            if value(var) > 0.5:
                _, mi, person, date_str = key
                meeting = sec["meetings"][mi]
                assignments.append({
                    "course": sec["course"],
                    "section": sec["section"],
                    "section_id": sid,
                    "meeting_index": mi,
                    "day_name": meeting["day_name"],
                    "start_hour": meeting["start_hour"],
                    "end_hour": meeting["end_hour"],
                    "start_time": meeting["start_time"],
                    "end_time": meeting["end_time"],
                    "room": meeting["room"],
                    "enrolment": sec["enrolment"],
                    "max_enrolment": sec["max_enrolment"],
                    "person": person,
                    "date": date_str,
                })

    # Determine coverage
    assigned_sections = {a["section_id"] for a in assignments}
    unassigned = [s for s in all_sections if s["section_id"] not in assigned_sections]

    # Per-course coverage
    course_sections: dict[str, list[dict]] = {}
    for sec in all_sections:
        course_sections.setdefault(sec["course"], []).append(sec)

    course_assigned: dict[str, int] = {}
    course_total: dict[str, int] = {}
    for code, secs in course_sections.items():
        course_total[code] = len(secs)
        course_assigned[code] = sum(1 for s in secs if s["section_id"] in assigned_sections)

    # Program-year coverage
    py_fully_covered = []
    py_partial = []
    py_none = []
    for code, pys in cover.items():
        total = course_total.get(code, 0)
        done = course_assigned.get(code, 0)
        for py in pys:
            if total == 0:
                py_none.append((py, code, 0, 0))
            elif done == total:
                py_fully_covered.append((py, code, done, total))
            elif done > 0:
                py_partial.append((py, code, done, total))
            else:
                py_none.append((py, code, 0, total))

    # Print schedules
    print("\n" + "=" * 80)
    print("SCHEDULES")
    print("=" * 80)

    for person_name in sorted(people.keys()):
        person_assignments = sorted(
            [a for a in assignments if a["person"] == person_name],
            key=lambda a: (a["date"], a["start_hour"])
        )
        print(f"\n--- {person_name}'s Schedule ({len(person_assignments)} visits) ---\n")
        if not person_assignments:
            print("  (no assignments)")
            continue
        print(f"  {'Date':<12} {'Day':<5} {'Time':<13} {'Room':<10} {'Course':<12} {'Section':<10} {'Covers':<30} {'Cohort':>6}")
        print(f"  {'─'*12} {'─'*5} {'─'*13} {'─'*10} {'─'*12} {'─'*10} {'─'*30} {'─'*6}")
        for a in person_assignments:
            pys = cover.get(a["course"], [])
            cohort = sum(cohorts.get(py, 0) for py in pys)
            d = datetime.strptime(a["date"], "%Y-%m-%d")
            print(f"  {a['date']:<12} {d.strftime('%a'):<5} {a['start_time']}-{a['end_time']:<8} {a['room']:<10} {a['course']:<12} {a['section']:<10} {', '.join(pys):<30} {cohort:>6}")

    # Coverage summary
    total_students = sum(cohorts.values())
    reachable = sum(cohorts.get(py, 0) for py, _, _, _ in py_fully_covered)
    partial_students = sum(cohorts.get(py, 0) for py, _, _, _ in py_partial)

    print("\n" + "=" * 80)
    print("COVERAGE SUMMARY")
    print("=" * 80)

    print(f"\n  Sections assigned: {len(assignments)} / {len(all_sections)}")
    print(f"  Sections unassigned: {len(unassigned)}")

    print(f"\n  Program-years FULLY covered ({len(py_fully_covered)}):")
    for py, code, done, total in sorted(py_fully_covered):
        print(f"    {py:<15} via {code:<12} ({done}/{total} sections) — {cohorts.get(py, 0)} students")

    if py_partial:
        print(f"\n  Program-years PARTIALLY covered ({len(py_partial)}):")
        for py, code, done, total in sorted(py_partial):
            print(f"    {py:<15} via {code:<12} ({done}/{total} sections) — {cohorts.get(py, 0)} students")

    if py_none:
        print(f"\n  Program-years NOT covered ({len(py_none)}):")
        for py, code, done, total in sorted(py_none):
            print(f"    {py:<15} via {code:<12} ({done}/{total} sections) — {cohorts.get(py, 0)} students")

    print(f"\n  Students fully reachable this period: {reachable} / {total_students}")
    print(f"  Students partially reachable: {partial_students}")

    # Backlog
    if unassigned:
        print("\n" + "=" * 80)
        print("BACKLOG (unassigned sections, ordered by cohort weight)")
        print("=" * 80)
        unassigned_with_weight = []
        for sec in unassigned:
            w = course_weight.get(sec["course"], 0)
            pys = cover.get(sec["course"], [])
            compatible_people = set()
            for opt in section_options.get(sec["section_id"], []):
                compatible_people.add(opt[1])
            meeting_strs = [f"{m['day_name']} {m['start_time']}-{m['end_time']} {m['room']}" for m in sec["meetings"]]
            unassigned_with_weight.append((w, sec, pys, compatible_people, meeting_strs))
        unassigned_with_weight.sort(key=lambda x: -x[0])

        print(f"\n  {'Course':<12} {'Section':<10} {'Meetings':<35} {'Weight':>6} {'Can attend':<20}")
        print(f"  {'─'*12} {'─'*10} {'─'*35} {'─'*6} {'─'*20}")
        for w, sec, pys, compat, mstrs in unassigned_with_weight:
            compat_str = ', '.join(sorted(compat)) if compat else "NOBODY"
            meetings_str = ' | '.join(mstrs)
            print(f"  {sec['course']:<12} {sec['section']:<10} {meetings_str:<35} {w:>6} {compat_str:<20}")

    # Per-course summary
    print("\n" + "=" * 80)
    print("PER-COURSE PROGRESS")
    print("=" * 80)
    print(f"\n  {'Course':<12} {'Assigned':>8} {'Total':>6} {'%':>5} {'Covers':<35} {'Weight':>6}")
    print(f"  {'─'*12} {'─'*8} {'─'*6} {'─'*5} {'─'*35} {'─'*6}")
    for code in sorted(cover.keys()):
        total = course_total.get(code, 0)
        done = course_assigned.get(code, 0)
        pct = f"{done/total*100:.0f}%" if total > 0 else "N/A"
        pys = ', '.join(cover[code])
        w = course_weight.get(code, 0)
        print(f"  {code:<12} {done:>8} {total:>6} {pct:>5} {pys:<35} {w:>6}")


if __name__ == "__main__":
    solve()
