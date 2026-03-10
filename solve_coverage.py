#!/usr/bin/env python3
"""
Solve the minimum lecture-section-visit set cover problem for UofT programs.

For each program-year, we need to "fully reach" every student by visiting
all sections of at least one top-level requirement item.

- AND nodes: pick cheapest branch (all students take both, so visiting one suffices)
- OR nodes: must visit ALL branches (students self-select)

Cost = number of in-person, non-9am LEC sections.
"""

import json
import time
import urllib.request
from itertools import combinations

API_BASE = "https://api.easi.utoronto.ca/ttb/getCoursesByCodeAndSectionCode"
# Try multiple sessions — 20259 for Fall, 20261 for Winter, 20259-20261 for full-year
SESSIONS = ["20259", "20261", "20259-20261"]

# ─── Program-year requirements ───
# Each program-year maps to a list of "top-level requirement items".
# Each item is either:
#   {"type": "single", "courses": ["CSC110Y1"]}
#   {"type": "and", "courses": ["MAT135H1", "MAT136H1"]}  — pick cheapest
#   {"type": "or", "courses": ["MAT137Y1", "MAT157Y1"]}   — must visit all

REQUIREMENTS = {
    # ── COMPUTER SCIENCE ──
    "CS-Y1": [
        {"type": "single", "courses": ["CSC110Y1"]},
        {"type": "single", "courses": ["CSC111H1"]},
        {"type": "or", "courses": ["MAT137Y1", "MAT157Y1"]},
    ],
    "CS-Y2": [
        {"type": "single", "courses": ["CSC207H1"]},
        {"type": "single", "courses": ["CSC209H1"]},
        {"type": "or", "courses": ["CSC236H1", "CSC240H1"]},
        {"type": "single", "courses": ["CSC258H1"]},
        {"type": "or", "courses": ["CSC263H1", "CSC265H1"]},
        {"type": "or", "courses": ["MAT223H1", "MAT240H1"]},
        {"type": "or", "courses": ["STA247H1", "STA237H1", "STA255H1", "STA257H1"]},
    ],
    "CS-Y3": [
        {"type": "single", "courses": ["CSC369H1"]},
        {"type": "single", "courses": ["CSC373H1"]},
    ],

    # ── MATHEMATICS ──
    "MATH-Y1": [
        {"type": "single", "courses": ["MAT157Y1"]},
        {"type": "single", "courses": ["MAT240H1"]},
        {"type": "single", "courses": ["MAT247H1"]},
    ],
    "MATH-Y2": [
        {"type": "single", "courses": ["MAT257Y1"]},
        {"type": "single", "courses": ["MAT267H1"]},
    ],
    "MATH-Y3": [
        {"type": "single", "courses": ["MAT327H1"]},
        {"type": "single", "courses": ["MAT347Y1"]},
        {"type": "single", "courses": ["MAT351Y1"]},
        {"type": "or", "courses": ["MAT354H1", "MAT357H1"]},
        {"type": "or", "courses": ["MAT363H1", "MAT367H1"]},
    ],
    "MATH-Y4": [
        {"type": "single", "courses": ["MAT477H1"]},
    ],

    # ── STATISTICS (Theory & Methods) ──
    "STAT-Y1": [
        {"type": "single", "courses": ["STA130H1"]},
        {"type": "or", "courses": ["CSC108H1", "CSC110Y1", "CSC111H1", "CSC148H1"]},
        {"type": "or", "courses": ["MAT137Y1", "MAT157Y1"]},
        {"type": "or", "courses": ["MAT223H1", "MAT224H1", "MAT240H1"]},
    ],
    "STAT-Y2": [
        {"type": "or", "courses": ["MAT224H1", "MAT247H1"]},
        {"type": "or", "courses": ["MAT237Y1", "MAT257Y1"]},
        {"type": "single", "courses": ["STA257H1"]},
        {"type": "single", "courses": ["STA261H1"]},
    ],
    "STAT-Y3": [
        {"type": "single", "courses": ["STA302H1"]},
        {"type": "single", "courses": ["STA303H1"]},
        {"type": "or", "courses": ["STA304H1", "STA305H1"]},
        {"type": "or", "courses": ["STA313H1", "STA314H1", "STA365H1"]},
        {"type": "single", "courses": ["STA347H1"]},
        {"type": "single", "courses": ["STA355H1"]},
    ],

    # ── DATA SCIENCE ──
    "DS-Y1": [
        {"type": "or", "courses": ["MAT137Y1", "MAT157Y1"]},
        {"type": "or", "courses": ["MAT223H1", "MAT240H1"]},
        {"type": "single", "courses": ["STA130H1"]},
        {"type": "or", "courses": ["CSC108H1", "CSC148H1", "CSC110Y1", "CSC111H1"]},
        # AND group: (CSC108+CSC148) OR (CSC110Y+CSC111) — but since it's OR at top level
        # students pick one path. Simplified: need all 4 courses' sections.
    ],
    "DS-Y2": [
        {"type": "or", "courses": ["MAT237Y1", "MAT257Y1"]},
        {"type": "single", "courses": ["STA257H1"]},
        {"type": "single", "courses": ["STA261H1"]},
        {"type": "single", "courses": ["CSC207H1"]},
        {"type": "or", "courses": ["CSC236H1", "CSC240H1"]},
        {"type": "single", "courses": ["JSC270H1"]},
    ],
    "DS-Y3": [
        {"type": "single", "courses": ["STA302H1"]},
        {"type": "or", "courses": ["STA303H1", "STA305H1"]},
        {"type": "single", "courses": ["STA355H1"]},
        {"type": "single", "courses": ["CSC209H1"]},
        {"type": "or", "courses": ["CSC263H1", "CSC265H1"]},
        {"type": "single", "courses": ["CSC343H1"]},
        {"type": "single", "courses": ["CSC373H1"]},
        {"type": "single", "courses": ["JSC370H1"]},
    ],

    # ── PHYSICS ──
    "PHYS-Y1": [
        {"type": "or", "courses": ["MAT137Y1", "MAT157Y1"]},  # simplified from MAT135+136/137/157
        {"type": "or", "courses": ["MAT223H1", "MAT240H1"]},
        {"type": "and", "courses": ["PHY131H1", "PHY151H1"]},  # AND: pick one pair
        {"type": "and", "courses": ["PHY132H1", "PHY152H1"]},
    ],
    "PHYS-Y2": [
        {"type": "or", "courses": ["MAT237Y1", "MAT257Y1", "MAT235Y1"]},
        {"type": "or", "courses": ["MAT244H1", "MAT267H1"]},
        {"type": "single", "courses": ["PHY224H1"]},
        {"type": "single", "courses": ["PHY250H1"]},
        {"type": "single", "courses": ["PHY252H1"]},
        {"type": "single", "courses": ["PHY254H1"]},
        {"type": "single", "courses": ["PHY256H1"]},
    ],
    "PHYS-Y3": [
        {"type": "single", "courses": ["APM346H1"]},
        {"type": "or", "courses": ["MAT334H1", "MAT354H1"]},
        {"type": "single", "courses": ["PHY350H1"]},
        {"type": "single", "courses": ["PHY354H1"]},
        {"type": "single", "courses": ["PHY356H1"]},
    ],

    # ── ENGINEERING SCIENCE (Years 1-2 common) ──
    "ENGSCI-Y1": [
        {"type": "single", "courses": ["CIV102H1"]},
        {"type": "single", "courses": ["ESC101H1"]},
        {"type": "single", "courses": ["ESC103H1"]},
        {"type": "single", "courses": ["ESC180H1"]},
        {"type": "single", "courses": ["ESC194H1"]},
        {"type": "single", "courses": ["PHY180H1"]},
        {"type": "single", "courses": ["ECE159H1"]},
        {"type": "single", "courses": ["ESC102H1"]},
        {"type": "single", "courses": ["ESC190H1"]},
        {"type": "single", "courses": ["ESC195H1"]},
        {"type": "single", "courses": ["MAT185H1"]},
        {"type": "single", "courses": ["MSE160H1"]},
    ],
    "ENGSCI-Y2": [
        {"type": "single", "courses": ["AER210H1"]},
        {"type": "single", "courses": ["CHE260H1"]},
        {"type": "single", "courses": ["ECE253H1"]},
        {"type": "single", "courses": ["ESC203H1"]},
        {"type": "single", "courses": ["MAT292H1"]},
        {"type": "single", "courses": ["PHY293H1"]},
        {"type": "single", "courses": ["BME205H1"]},
        {"type": "single", "courses": ["ECE259H1"]},
        {"type": "single", "courses": ["ESC204H1"]},
        {"type": "single", "courses": ["MIE286H1"]},
        {"type": "single", "courses": ["PHY294H1"]},
    ],

    # ── NEUROSCIENCE ──
    "NEURO-Y1": [
        {"type": "and", "courses": ["CHM135H1", "CHM136H1"]},  # or CHM151Y1 but AND
        {"type": "and", "courses": ["BIO120H1", "BIO130H1"]},
        {"type": "single", "courses": ["PSY100H1"]},
    ],
    "NEURO-Y2": [
        {"type": "single", "courses": ["BCH210H1"]},
        {"type": "or", "courses": ["BIO230H1", "BIO255H1"]},
        {"type": "or", "courses": ["HMB265H1", "BIO260H1"]},
        {"type": "single", "courses": ["PSL300H1"]},
        {"type": "single", "courses": ["HMB200H1"]},
        {"type": "single", "courses": ["STA288H1"]},
    ],
    "NEURO-Y3": [
        {"type": "single", "courses": ["HMB300H1"]},
        {"type": "single", "courses": ["CJH332H1"]},
        {"type": "single", "courses": ["HMB320H1"]},
        {"type": "or", "courses": ["HMB306H1", "HMB406H1", "PHL281H1"]},
        {"type": "or", "courses": ["HMB310H1", "HMB314H1", "PSY369H1"]},
    ],

    # ── COGNITIVE SCIENCE ──
    "COGSCI-Y1": [
        {"type": "or", "courses": ["CSC108H1", "CSC110Y1"]},
        {"type": "or", "courses": ["CSC111H1", "CSC148H1"]},
        {"type": "or", "courses": ["MAT137Y1", "MAT157Y1"]},  # simplified
    ],
    "COGSCI-Y2": [
        {"type": "single", "courses": ["COG250Y1"]},
        {"type": "or", "courses": ["STA220H1", "STA237H1", "STA247H1", "STA255H1", "STA257H1", "PSY201H1"]},
        {"type": "single", "courses": ["PSY270H1"]},
    ],
    "COGSCI-Y3": [
        {"type": "single", "courses": ["PSY290H1"]},
        {"type": "single", "courses": ["PHL342H1"]},
    ],

    # ── ECONOMICS ──
    "ECON-Y1": [
        {"type": "single", "courses": ["ECO101H1"]},
        {"type": "single", "courses": ["ECO102H1"]},
        {"type": "or", "courses": ["MAT137Y1", "MAT157Y1"]},  # simplified
    ],
    "ECON-Y2": [
        {"type": "single", "courses": ["ECO206Y1"]},
        {"type": "single", "courses": ["ECO208Y1"]},
        {"type": "or", "courses": ["ECO220Y1", "ECO227Y1"]},
        # STA257+STA261 also an option but already OR with ECO courses
    ],
    "ECON-Y3": [
        {"type": "single", "courses": ["ECO325H1"]},
        {"type": "single", "courses": ["ECO326H1"]},
        {"type": "single", "courses": ["ECO375H1"]},
    ],
}


def fetch_course(code: str) -> list[dict]:
    """Fetch course data from UofT API. Returns list of course objects."""
    url = f"{API_BASE}/{code}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        courses = data.get("payload", {}).get("pageableCourse", {}).get("courses", [])
        return courses
    except Exception as e:
        print(f"  ERROR fetching {code}: {e}")
        return []


def count_eligible_sections(code: str) -> int:
    """
    Count in-person LEC sections that don't start at 9am.
    A section qualifies if:
    - teachMethod == "LEC"
    - deliveryMode includes "INPER"
    - cancelInd != "Y"
    - No meeting time starts at 9am (32400000 ms)
    """
    courses = fetch_course(code)
    count = 0
    for course in courses:
        # Only St. George campus
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
            # Check delivery mode
            modes = [dm.get("mode") for dm in section.get("deliveryModes", [])]
            if "INPER" not in modes:
                continue
            # Check for 9am start
            meeting_times = section.get("meetingTimes", [])
            has_9am = any(
                mt.get("start", {}).get("millisofday") == 32400000
                for mt in meeting_times
            )
            if has_9am:
                continue
            count += 1
    return count


def get_item_cost(item: dict, section_cache: dict[str, int]) -> int | None:
    """
    Calculate the visit cost for a requirement item.
    - single: sections of that course
    - and: min sections across branches (pick cheapest)
    - or: sum of sections across all branches (must visit all)
    Returns None if any course has 0 sections (can't reach students).
    """
    costs = []
    for code in item["courses"]:
        if code not in section_cache:
            return None  # shouldn't happen
        costs.append(section_cache[code])

    if item["type"] == "single":
        return costs[0] if costs[0] > 0 else None
    elif item["type"] == "and":
        # Pick cheapest branch
        valid = [c for c in costs if c > 0]
        return min(valid) if valid else None
    elif item["type"] == "or":
        # Must visit all branches — but skip branches with 0 sections
        # (if a branch has 0 sections, no students can be in it)
        total = sum(costs)
        return total if total > 0 else None
    return None


def solve():
    # Step 1: Collect all unique course codes
    all_courses = set()
    for items in REQUIREMENTS.values():
        for item in items:
            for code in item["courses"]:
                all_courses.add(code)

    print(f"Total unique courses to query: {len(all_courses)}")

    # Step 2: Fetch section counts
    section_cache: dict[str, int] = {}
    for i, code in enumerate(sorted(all_courses)):
        print(f"  [{i+1}/{len(all_courses)}] {code}...", end=" ", flush=True)
        count = count_eligible_sections(code)
        section_cache[code] = count
        print(f"{count} sections")
        time.sleep(0.1)  # polite rate limiting

    # Save cache
    with open("section_cache.json", "w") as f:
        json.dump(section_cache, f, indent=2)
    print(f"\nSection cache saved to section_cache.json")

    # Step 3: Compute costs for each requirement item per program-year
    print("\n=== REQUIREMENT ITEM COSTS ===\n")
    # For each program-year, list of (item_index, cost, item_description)
    py_options: dict[str, list[tuple[int, int, str]]] = {}

    for py, items in REQUIREMENTS.items():
        py_options[py] = []
        for idx, item in enumerate(items):
            cost = get_item_cost(item, section_cache)
            desc = f"{item['type'].upper()}({', '.join(item['courses'])})"
            if cost is not None and cost > 0:
                py_options[py].append((idx, cost, desc))
                print(f"  {py} item {idx}: cost={cost}  {desc}")
            else:
                print(f"  {py} item {idx}: UNAVAILABLE  {desc}")

    # Step 4: Build set cover instance
    # Universe = all program-years
    # For each requirement item, it covers the program-year it belongs to.
    # But courses are SHARED across program-years!
    # So we need to think about it differently:
    #
    # A "candidate" is: pick one specific item from a program-year.
    # The cost is the item's cost.
    # It covers that program-year.
    # But if another program-year has an item with identical or subset courses,
    # visiting those sections also covers that other program-year.
    #
    # More precisely: if we visit all sections of course X, then any program-year
    # that has a "single" item with course X is covered.
    # For "and" items: if we visit the chosen branch, it's covered.
    # For "or" items: we need ALL branches visited.
    #
    # This is complex. Let's simplify:
    # Build a mapping from "set of courses we commit to visiting" -> program-years covered.
    # Then find minimum cost collection covering all program-years.

    # Actually, let's think about it as:
    # Decision: for each program-year, pick exactly one requirement item.
    # Cost of that pick = item cost (sections to visit).
    # But if two picks share courses, we don't double-count.
    # Total cost = |union of all sections we need to visit|.
    #
    # Since courses are the atomic unit, total cost = sum of section counts
    # for the union of all courses we need to visit.
    #
    # For AND items: we pick one branch course.
    # For OR items: we need all branch courses.
    # For single items: we need that one course.
    #
    # So the decision for each program-year is: which item to use?
    # For AND items, also: which branch?

    # Let's enumerate: for each program-year, the choices.
    # A choice = frozenset of courses we must visit.

    print("\n=== BUILDING OPTIMIZATION MODEL ===\n")

    # For each program-year, enumerate possible "coverage sets" (sets of courses)
    py_choices: dict[str, list[tuple[frozenset[str], str]]] = {}
    for py, items in REQUIREMENTS.items():
        choices = []
        for idx, item in enumerate(items):
            desc = f"{item['type'].upper()}({', '.join(item['courses'])})"
            if item["type"] == "single":
                c = item["courses"][0]
                if section_cache.get(c, 0) > 0:
                    choices.append((frozenset([c]), desc))
            elif item["type"] == "and":
                # Pick the cheapest branch
                for c in item["courses"]:
                    if section_cache.get(c, 0) > 0:
                        choices.append((frozenset([c]), f"AND_PICK({c}) from {desc}"))
            elif item["type"] == "or":
                # Must visit all branches
                courses_needed = frozenset(
                    c for c in item["courses"] if section_cache.get(c, 0) > 0
                )
                if courses_needed:
                    choices.append((courses_needed, desc))
        py_choices[py] = choices
        if not choices:
            print(f"  WARNING: {py} has NO viable coverage options!")

    # Now solve: pick one choice per program-year to minimize
    # total sections = sum(section_cache[c] for c in union_of_all_chosen_courses)

    all_pys = list(REQUIREMENTS.keys())
    n = len(all_pys)
    print(f"Program-years to cover: {n}")
    for py in all_pys:
        print(f"  {py}: {len(py_choices[py])} choices")

    # Brute force: iterate over all combinations of choices.
    # Number of combinations = product of choices per PY.
    total_combos = 1
    for py in all_pys:
        total_combos *= max(len(py_choices[py]), 1)
    print(f"Total combinations: {total_combos:,}")

    if total_combos > 50_000_000:
        print("Too many combinations for brute force. Using greedy approach.")
        solve_greedy(all_pys, py_choices, section_cache)
        return

    # Brute force with recursive enumeration
    best_cost = float('inf')
    best_assignment = None

    choice_lists = [py_choices[py] for py in all_pys]
    # Use indices
    choice_indices = [list(range(len(cl))) for cl in choice_lists]

    def recurse(depth: int, courses_so_far: frozenset[str], assignment: list[int]):
        nonlocal best_cost, best_assignment

        if depth == n:
            cost = sum(section_cache[c] for c in courses_so_far)
            if cost < best_cost:
                best_cost = cost
                best_assignment = list(assignment)
            return

        # Pruning: current cost already >= best
        current_cost = sum(section_cache[c] for c in courses_so_far)
        if current_cost >= best_cost:
            return

        py = all_pys[depth]
        choices = choice_lists[depth]
        if not choices:
            # No viable option — skip (can't cover this PY)
            recurse(depth + 1, courses_so_far, assignment + [-1])
            return

        for i, (course_set, desc) in enumerate(choices):
            new_courses = courses_so_far | course_set
            recurse(depth + 1, new_courses, assignment + [i])

    print("\nSolving (brute force with pruning)...")
    recurse(0, frozenset(), [])

    # Output results
    print("\n" + "=" * 70)
    print("OPTIMAL SOLUTION")
    print("=" * 70)

    if best_assignment is None:
        print("No feasible solution found!")
        return

    # Collect results
    all_visited_courses: set[str] = set()
    results = []
    for i, py in enumerate(all_pys):
        choice_idx = best_assignment[i]
        if choice_idx == -1:
            results.append((py, None, set(), "NO VIABLE OPTION"))
            continue
        course_set, desc = choice_lists[i][choice_idx]
        all_visited_courses |= course_set
        item_cost = sum(section_cache[c] for c in course_set)
        results.append((py, desc, course_set, item_cost))

    # Group by course to show which PYs each course covers
    course_to_pys: dict[str, list[str]] = {}
    for py, desc, courses, cost in results:
        for c in courses:
            course_to_pys.setdefault(c, []).append(py)

    print(f"\nTotal unique courses to visit: {len(all_visited_courses)}")
    print(f"Total sections (visits): {best_cost}")

    print("\n--- Per program-year selection ---\n")
    for py, desc, courses, cost in results:
        print(f"  {py}: {desc}")
        if courses:
            for c in sorted(courses):
                print(f"    - {c}: {section_cache[c]} sections")
            print(f"    Item cost: {cost} visits")

    print("\n--- Per course summary ---\n")
    for c in sorted(all_visited_courses):
        pys = course_to_pys.get(c, [])
        print(f"  {c}: {section_cache[c]} sections — covers: {', '.join(pys)}")

    print(f"\n--- TOTAL MINIMUM VISITS: {best_cost} ---")

    # Flag expensive OR groups
    print("\n--- HIGH-COST OR GROUPS (flagged for human review) ---\n")
    for py, items in REQUIREMENTS.items():
        for item in items:
            if item["type"] == "or" and len(item["courses"]) >= 3:
                cost = get_item_cost(item, section_cache)
                if cost and cost > 5:
                    print(f"  {py}: OR({', '.join(item['courses'])}) — cost={cost} visits")


def solve_greedy(all_pys, py_choices, section_cache):
    """Greedy fallback for large instances."""
    uncovered = set(all_pys)
    total_courses = set()
    assignment = {}

    while uncovered:
        best_ratio = float('inf')
        best_py = None
        best_choice = None

        for py in uncovered:
            for course_set, desc in py_choices[py]:
                new_courses = course_set - total_courses
                marginal_cost = sum(section_cache[c] for c in new_courses)
                # Covers 1 PY for marginal_cost
                ratio = marginal_cost  # since it covers exactly 1
                if ratio < best_ratio:
                    best_ratio = ratio
                    best_py = py
                    best_choice = (course_set, desc)

        if best_py is None:
            print(f"Cannot cover: {uncovered}")
            break

        assignment[best_py] = best_choice
        total_courses |= best_choice[0]
        uncovered.remove(best_py)

    total = sum(section_cache[c] for c in total_courses)
    print(f"\nGreedy solution: {total} total visits")
    for py in all_pys:
        if py in assignment:
            cs, desc = assignment[py]
            cost = sum(section_cache[c] for c in cs)
            print(f"  {py}: {desc} (cost={cost})")


if __name__ == "__main__":
    solve()
