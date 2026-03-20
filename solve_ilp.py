#!/usr/bin/env python3
"""
Solve the minimum lecture-visit set cover via ILP.

Decision variables:
  x[py][i] = 1 if we pick choice i for program-year py
  y[c] = 1 if course c is in the union of visited courses

Objective: minimize sum(sections[c] * y[c])

Constraints:
  - For each py: sum(x[py][i]) >= 1 (must pick at least one item)
  - For each (py, i, c): y[c] >= x[py][i] if c is in choice i's course set
"""

import json
from itertools import product

# Load section cache
with open("section_cache.json") as f:
    SECTIONS: dict[str, int] = json.load(f)

# Requirements
REQUIREMENTS = {
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
        {"type": "single", "courses": ["MAT354H1"]},
        {"type": "single", "courses": ["MAT357H1"]},
        {"type": "or", "courses": ["MAT363H1", "MAT367H1"]},
    ],
    "MATH-Y4": [
        {"type": "single", "courses": ["MAT477H1"]},
    ],
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
        {"type": "or", "courses": ["STA447H1", "STA452H1", "STA453H1"]},
    ],
    "DS-Y1": [
        {"type": "or", "courses": ["MAT137Y1", "MAT157Y1"]},
        {"type": "or", "courses": ["MAT223H1", "MAT240H1"]},
        {"type": "single", "courses": ["STA130H1"]},
        {"type": "or", "courses": ["CSC108H1", "CSC148H1"]},
        {"type": "or", "courses": ["CSC110Y1", "CSC111H1"]},
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
        {"type": "or", "courses": ["STA314H1", "CSC311H1"]},
        {"type": "single", "courses": ["CSC209H1"]},
        {"type": "or", "courses": ["CSC263H1", "CSC265H1"]},
        {"type": "single", "courses": ["CSC343H1"]},
        {"type": "single", "courses": ["CSC373H1"]},
        {"type": "single", "courses": ["JSC370H1"]},
    ],
    "PHYS-Y1": [
        {"type": "or", "courses": ["MAT135H1", "MAT136H1"]},
        {"type": "or", "courses": ["MAT137Y1", "MAT157Y1"]},
        {"type": "or", "courses": ["MAT223H1", "MAT240H1"]},
        {"type": "or", "courses": ["PHY131H1", "PHY151H1"]},
        {"type": "or", "courses": ["PHY132H1", "PHY152H1"]},
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
    "COGSCI-Y1": [
        {"type": "or", "courses": ["CSC108H1", "CSC110Y1"]},
        {"type": "or", "courses": ["CSC111H1", "CSC148H1"]},
        {"type": "or", "courses": ["MAT135H1", "MAT136H1"]},
        {"type": "or", "courses": ["MAT137Y1", "MAT157Y1"]},
    ],
    "COGSCI-Y2": [
        {"type": "single", "courses": ["COG250Y1"]},
        {"type": "or", "courses": ["STA220H1", "STA237H1", "STA247H1", "STA255H1", "STA257H1", "PSY201H1"]},
        {"type": "single", "courses": ["PSY270H1"]},
    ],
    "COGSCI-Y3": [
        {"type": "single", "courses": ["PSY290H1"]},
        {"type": "single", "courses": ["PHL342H1"]},
        {"type": "single", "courses": ["BIO220H1"]},
    ],
    "COGSCI-Y4": [
        {"type": "or", "courses": ["COG402H1", "COG403H1", "COG404H1", "COG498H1", "COG499H1"]},
    ],
    "ECON-Y1": [
        {"type": "single", "courses": ["ECO101H1"]},
        {"type": "single", "courses": ["ECO102H1"]},
        {"type": "or", "courses": ["MAT135H1", "MAT136H1"]},
        {"type": "or", "courses": ["MAT137Y1", "MAT157Y1"]},
    ],
    "ECON-Y2": [
        {"type": "single", "courses": ["ECO206Y1"]},
        {"type": "single", "courses": ["ECO208Y1"]},
        {"type": "or", "courses": ["ECO220Y1", "ECO227Y1", "STA261H1"]},
    ],
    "ECON-Y3": [
        {"type": "single", "courses": ["ECO325H1"]},
        {"type": "single", "courses": ["ECO326H1"]},
        {"type": "single", "courses": ["ECO375H1"]},
    ],
    "ENG-Y1": [
        {"type": "or", "courses": ["APS105H1", "APS106H1"]},
        {"type": "single", "courses": ["APS112H1"]},
        {"type": "single", "courses": ["ECE110H1"]},
        {"type": "single", "courses": ["MAT187H1"]},
        {"type": "single", "courses": ["MIE100H1"]},
        {"type": "single", "courses": ["CIV100H1"]},
        {"type": "single", "courses": ["MAT186H1"]},
        {"type": "single", "courses": ["MAT188H1"]},
    ],
    "ECE-Y2": [
        {"type": "single", "courses": ["ECE212H1"]},
        {"type": "single", "courses": ["ECE216H1"]},
        {"type": "single", "courses": ["ECE221H1"]},
        {"type": "single", "courses": ["ECE243H1"]},
        {"type": "or", "courses": ["ECE295H1", "ECE297H1"]},
    ],
    "ECE-Y3": [
        {"type": "or", "courses": ["ECE302H1", "ECE311H1"]},
        {"type": "or", "courses": ["ECE342H1", "ECE344H1", "ECE345H1", "ECE350H1", "ECE361H1"]},
    ],
    "INDE-Y2": [
        {"type": "single", "courses": ["MIE223H1"]},
        {"type": "single", "courses": ["MIE237H1"]},
        {"type": "single", "courses": ["MIE240H1"]},
        {"type": "single", "courses": ["MIE245H1"]},
        {"type": "single", "courses": ["MIE263H1"]},
    ],
    "INDE-Y3": [
        {"type": "single", "courses": ["MIE350H1"]},
        {"type": "single", "courses": ["MIE359H1"]},
        {"type": "single", "courses": ["MIE363H1"]},
    ],
}


def expand_choices(item: dict) -> list[frozenset[str]]:
    """
    Expand a requirement item into possible course-set choices.
    - single: one choice = {course}
    - and: one choice per branch = {branch_course} (pick cheapest)
    - or: one choice = {all branches} (must visit all)
    Only include courses with >0 sections.
    """
    if item["type"] == "single":
        c = item["courses"][0]
        if SECTIONS.get(c, 0) > 0:
            return [frozenset([c])]
        return []
    elif item["type"] == "and":
        choices = []
        for c in item["courses"]:
            if SECTIONS.get(c, 0) > 0:
                choices.append(frozenset([c]))
        return choices
    elif item["type"] == "or":
        valid = [c for c in item["courses"] if SECTIONS.get(c, 0) > 0]
        if valid:
            return [frozenset(valid)]
        return []
    return []


def cost_of(course_set: frozenset[str]) -> int:
    return sum(SECTIONS.get(c, 0) for c in course_set)


def solve():
    # Build choices per program-year
    py_choices: dict[str, list[tuple[frozenset[str], str]]] = {}
    for py, items in REQUIREMENTS.items():
        choices = []
        for item in items:
            desc = f"{item['type'].upper()}({', '.join(item['courses'])})"
            for cs in expand_choices(item):
                if item["type"] == "and":
                    # Label which branch we picked
                    branch = list(cs)[0]
                    choices.append((cs, f"AND_PICK({branch})"))
                else:
                    choices.append((cs, desc))
        py_choices[py] = choices

    # Check feasibility
    infeasible = []
    for py, choices in py_choices.items():
        if not choices:
            infeasible.append(py)
            print(f"WARNING: {py} has NO viable options — cannot be covered")

    feasible_pys = [py for py in REQUIREMENTS if py not in infeasible]

    solve_with_pulp(feasible_pys, py_choices)


def solve_with_pulp(feasible_pys, py_choices):
    from pulp import LpMinimize, LpProblem, LpVariable, lpSum, LpBinary, value, LpStatus

    prob = LpProblem("MinLectureVisits", LpMinimize)

    # Collect all courses that appear in any choice
    all_courses = set()
    for py in feasible_pys:
        for cs, _ in py_choices[py]:
            all_courses |= cs

    # Variables
    # x[py][i] = 1 if we pick choice i for program-year py
    x = {}
    for py in feasible_pys:
        x[py] = {}
        for i in range(len(py_choices[py])):
            x[py][i] = LpVariable(f"x_{py}_{i}", cat=LpBinary)

    # y[c] = 1 if course c is visited
    y = {}
    for c in all_courses:
        y[c] = LpVariable(f"y_{c}", cat=LpBinary)

    # Objective: minimize total sections
    prob += lpSum(SECTIONS[c] * y[c] for c in all_courses)

    # Constraint: pick at least one choice per PY
    for py in feasible_pys:
        prob += lpSum(x[py][i] for i in range(len(py_choices[py]))) >= 1

    # Constraint: if choice i is picked, all its courses must be visited
    for py in feasible_pys:
        for i, (cs, _) in enumerate(py_choices[py]):
            for c in cs:
                prob += y[c] >= x[py][i]

    # Solve
    prob.solve()

    print(f"\nSolver status: {LpStatus[prob.status]}")
    print(f"Optimal total visits: {int(value(prob.objective))}")

    # Extract solution
    print("\n" + "=" * 70)
    print("OPTIMAL SOLUTION")
    print("=" * 70)

    visited_courses = set()
    course_covers: dict[str, list[str]] = {}

    for py in feasible_pys:
        for i, (cs, desc) in enumerate(py_choices[py]):
            if value(x[py][i]) > 0.5:
                visited_courses |= cs
                for c in cs:
                    course_covers.setdefault(c, []).append(py)
                cost = cost_of(cs)
                print(f"\n  {py}: {desc}")
                for c in sorted(cs):
                    print(f"    {c}: {SECTIONS[c]} sections")
                print(f"    → {cost} visits for this item")
                break  # only show first picked choice

    # Show infeasible
    for py in REQUIREMENTS:
        if py not in feasible_pys:
            print(f"\n  {py}: *** INFEASIBLE — no available sections ***")

    # Course summary with sharing
    print("\n" + "=" * 70)
    print("COURSE VISIT SUMMARY (with cross-program sharing)")
    print("=" * 70)

    total = 0
    for c in sorted(visited_courses):
        pys = course_covers.get(c, [])
        s = SECTIONS[c]
        total += s
        print(f"  {c}: {s} sections — reaches: {', '.join(pys)}")

    print(f"\n  TOTAL VISITS: {total}")

    # Flag expensive OR groups
    print("\n" + "=" * 70)
    print("HIGH-COST OR GROUPS (flagged for human review)")
    print("=" * 70)

    for py, items in REQUIREMENTS.items():
        for item in items:
            if item["type"] == "or":
                valid = [c for c in item["courses"] if SECTIONS.get(c, 0) > 0]
                cost = sum(SECTIONS.get(c, 0) for c in valid)
                if cost >= 7:
                    print(f"  {py}: OR({', '.join(valid)}) — {cost} visits to cover all branches")

    # Show which PYs have no low-cost option
    print("\n" + "=" * 70)
    print("PROGRAM-YEAR MINIMUM COSTS (cheapest single item)")
    print("=" * 70)

    for py in sorted(REQUIREMENTS.keys()):
        if py not in feasible_pys:
            print(f"  {py}: INFEASIBLE")
            continue
        min_cost = min(cost_of(cs) for cs, _ in py_choices[py])
        max_cost = max(cost_of(cs) for cs, _ in py_choices[py])
        print(f"  {py}: min={min_cost}, max={max_cost} ({len(py_choices[py])} options)")


if __name__ == "__main__":
    solve()
