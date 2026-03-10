# University of Toronto Timetable API Guide

Base URL: `https://api.easi.utoronto.ca/ttb/`

This is the backend API for the official Timetable Builder (ttb.utoronto.ca). It is public, unauthenticated, and returns JSON when you set `Accept: application/json`.

## Endpoints

### 1. GET /reference-data

Returns valid values for sessions, divisions, campuses, course levels, delivery modes, etc.

```bash
curl -s "https://api.easi.utoronto.ca/ttb/reference-data" -H "Accept: application/json"
```

Key data returned:
- **currentSessions**: List of active academic sessions with codes
- **divisions**: Faculties (e.g. ARTSC = Arts & Science, APSC = Engineering)
- **campuses**: "St. George", "Scarborough", "University of Toronto at Mississauga"

### Session codes

| Code | Meaning |
|------|---------|
| `20259` | Fall 2025 |
| `20261` | Winter 2026 |
| `20259-20261` | Fall-Winter 2025-2026 (full year) |
| `20265` | Summer 2026 (full session) |
| `20265F` | Summer 2026 first sub-session |
| `20265S` | Summer 2026 second sub-session |

Pattern: `YYYY` + `M` where M is 9=Fall, 1=Winter, 5=Summer.

### 2. GET /getCoursesByCodeAndSectionCode/{courseCode}

Returns full course data including all sections, meeting times, rooms, instructors, and enrolment. This is the most useful endpoint for getting complete data for a known course.

```bash
curl -s "https://api.easi.utoronto.ca/ttb/getCoursesByCodeAndSectionCode/CSC108H1" \
  -H "Accept: application/json"
```

Optional query param: `?sectionCode=F` to filter by section (F=Fall, S=Winter, Y=Year).

#### Response structure

```json
{
  "payload": {
    "pageableCourse": {
      "courses": [
        {
          "id": "67f998c7de40c67f1da33599",
          "name": "Introduction to Computer Programming",
          "code": "CSC108H1",
          "sectionCode": "F",
          "campus": "St. George",
          "sessions": ["20259"],
          "sections": [
            {
              "name": "LEC0401",
              "type": "Lecture",
              "teachMethod": "LEC",
              "sectionNumber": "0401",
              "meetingTimes": [
                {
                  "start": { "day": 1, "millisofday": 54000000 },
                  "end": { "day": 1, "millisofday": 57600000 },
                  "building": {
                    "buildingCode": "MP",
                    "buildingRoomNumber": "203",
                    "buildingRoomSuffix": "",
                    "buildingUrl": "https://map.utoronto.ca/?id=1809#!m/494490",
                    "buildingName": null
                  },
                  "sessionCode": "20259",
                  "repetition": "WEEKLY",
                  "repetitionTime": "ONCE_A_WEEK"
                }
              ],
              "instructors": [
                { "firstName": "Samarendra Chandan Bind", "lastName": "Dash" }
              ],
              "currentEnrolment": 168,
              "maxEnrolment": 196,
              "cancelInd": "N",
              "waitlistInd": "Y",
              "currentWaitlist": 0,
              "deliveryModes": [
                { "session": "20259", "mode": "INPER" }
              ]
            }
          ]
        }
      ]
    }
  }
}
```

#### Interpreting meeting times

- `start.day`: 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday, 7=Sunday
- `start.millisofday` / `end.millisofday`: Milliseconds since midnight. Divide by 3,600,000 to get hours.
  - 32400000 = 9:00, 36000000 = 10:00, 39600000 = 11:00, 43200000 = 12:00
  - 46800000 = 13:00, 50400000 = 14:00, 54000000 = 15:00, 57600000 = 16:00
  - 61200000 = 17:00, 64800000 = 18:00, 68400000 = 19:00, 72000000 = 20:00

#### teachMethod values

| Code | Meaning |
|------|---------|
| `LEC` | Lecture |
| `TUT` | Tutorial |
| `PRA` | Practical |

### 3. GET /getOptimizedMatchingCourseTitles

Search/autocomplete for courses by prefix. Useful for discovering all course codes in a department.

```bash
curl -s "https://api.easi.utoronto.ca/ttb/getOptimizedMatchingCourseTitles?term=CSC&divisions=ARTSC&sessions=20259&lowerThreshold=50&upperThreshold=500" \
  -H "Accept: application/json"
```

Parameters:
- `term`: Search string (course code prefix like "CSC", "MAT", "PHL")
- `divisions`: Faculty code (comma-separated if multiple)
- `sessions`: Session code (comma-separated if multiple)
- `lowerThreshold`: Min results before fetching from server (use 50)
- `upperThreshold`: Max results to return (use 500+ to get all)

Returns a list of `{ code, sectionCode, name, description, sessions, division, rank }` objects.

### 4. POST /getPageableCourses

Search with filters and pagination. Useful for broad queries. Requires `Content-Type: application/json`.

```bash
curl -s -X POST "https://api.easi.utoronto.ca/ttb/getPageableCourses" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "courseCodeAndTitleProps": {
      "courseCode": "",
      "courseTitle": "",
      "courseSectionCode": "",
      "searchCourseDescription": false
    },
    "departmentProps": [],
    "campuses": ["St. George"],
    "sessions": ["20259"],
    "requirementProps": [],
    "instructor": "",
    "courseLevels": [],
    "deliveryModes": [],
    "dayPreferences": [],
    "timePreferences": [],
    "divisions": ["ARTSC"],
    "creditWeights": [],
    "page": 1,
    "pageSize": 50,
    "direction": "asc"
  }'
```

Note: `divisions` must be non-empty for this endpoint to return results.

## Recommended workflow for bulk data collection

1. Call `/getOptimizedMatchingCourseTitles` with a department prefix (e.g. "CSC") to get all course codes
2. For each course code, call `/getCoursesByCodeAndSectionCode/{code}` to get full section/time/room data
3. Filter sections by `teachMethod == "LEC"` if you only want lectures

## Department prefixes for target majors

| Major | Prefix(es) |
|-------|-----------|
| Computer Science | CSC |
| Mathematics | MAT |
| Philosophy | PHL |
| Economics | ECO |
| Physics | PHY |

## Notes

- No API key or authentication required
- No observed rate limiting, but be polite (add small delays between requests)
- The old API at `timetable.iit.artsci.utoronto.ca` is defunct (DNS no longer resolves)
- All data covers St. George, UTM, and UTSC campuses
- Summer session data may have TBA rooms/instructors until closer to the term
