# Python Basics — Zero-to-Robot Curriculum

Eight short assignments that take a student with **no programming experience**
to the point where they can read and modify the scripts in
[`examples/`](../examples/). Each assignment is designed to take **30–60
minutes** and builds directly on the one before it.

This is separate from `examples/`, which teaches the platform-specific
robot API (motors, sensors, PID, etc.). This folder teaches the Python
language itself. Assignment 8 explicitly bridges the two, ending with the
student reading `examples/01_drive.py` and `examples/05_obstacle_avoidance.py`
and explaining what each line does.

## How each assignment is packaged

Every lesson folder contains three files:

| File | Purpose |
|---|---|
| `instructions.html` | Paste directly into a Canvas Page using the HTML editor ("</> HTML Editor" button in the Rich Content Editor). Self-contained, inline-styled, no external assets or `<script>` tags — safe for Canvas's sanitizer. |
| `starter.py` | Give this to students (e.g. as a file download / linked in the same Canvas page). They edit it in place to complete the `TODO`s and run it from a terminal on the Pi with `python3 starter.py`. |
| `solution.py` | Instructor answer key. Not for students. |

## Sequence

1. **01 — Hello, Python**: `print()`, comments, running a script, reading errors.
2. **02 — Variables & Numbers**: variables, `int`/`float`, arithmetic operators, `+=`.
3. **03 — Strings & Input**: string basics, f-strings, `input()`, type conversion.
4. **04 — Conditionals**: comparisons, booleans, `if`/`elif`/`else`, `and`/`or`/`not`.
5. **05 — While Loops**: `while`, counters, accumulators, `break` — the pattern behind every robot control loop.
6. **06 — For Loops & Lists**: lists, indexing, `for` over a list and over `range()`.
7. **07 — Functions**: `def`, parameters, `return`, why functions exist.
8. **08 — Objects & Methods**: dot notation, attributes vs. methods, then reading real robot code.

## Running a script on the Pi

Students run each assignment from a terminal:

```bash
python3 starter.py
```

They should re-run after every edit — the instructions page tells them what
output to expect at each step, since there is no auto-grader.

## Using this with Canvas

1. Open the lesson's `instructions.html` in a text editor, select all, copy.
2. In Canvas: **Pages → + Page**, then in the Rich Content Editor toolbar click
   the `</>` (HTML Editor) button, paste, switch back to the visual editor to
   confirm it rendered, then **Save & Publish**.
3. Attach or link `starter.py` as a file on the same page for students to
   download.
4. Keep `solution.py` out of the student-facing module.
