"""Assignment 6 Practice — Debug It

Seven numbered bugs. Some of them would crash the program, so they're
written as comments — read them, figure out what error they'd cause and
why, then try fixing them on paper (or uncomment and fix them for real).
The rest are "live" — they run without crashing, but print the wrong
thing. Find out why before you check practice_debug_solution.py.

    python3 practice_debug.py

This file exits cleanly (no crash) as distributed.
"""

# --- Bug 1 ---
# Goal: print the last waypoint in the list (55).
# This crashes with IndexError, because len(waypoints) is 4, and the
# valid indices for a 4-item list are only 0, 1, 2, 3 — index 4 doesn't
# exist.
# waypoints = [10, 25, 40, 55]
# print(waypoints[len(waypoints)])

# --- Bug 2 ---
# Goal: print each reading in the list, one per line.
print("Bug 2:")
readings = [12, 18, 25, 9]
last_value = 0
for reading in readings:
    print(last_value)  # bug: prints last_value every time, not reading

# --- Bug 3 ---
# Goal: build up a list of squares: [1, 4, 9]
# This crashes with AttributeError. squares.append(1) adds 1 to the list
# AND returns None, so "squares = squares.append(1)" overwrites squares
# with None. The next line then tries to call .append() on None, which
# has no such method.
# squares = []
# squares = squares.append(1)
# squares = squares.append(4)
# squares = squares.append(9)
# print(squares)

# --- Bug 4 ---
# Goal: print "Lap 1" through "Lap 5" (five laps total).
print("Bug 4:")
for lap in range(1, 5):
    print(f"Lap {lap}")

# --- Bug 5 ---
# Goal: build a list of doubled values: [2, 4, 6]
# This crashes with NameError. "doubled" is never created with
# doubled = [] before the loop, so Python has no variable named
# doubled to append onto.
# for n in [1, 2, 3]:
#     doubled.append(n * 2)
# print(doubled)

# --- Bug 6 ---
# Goal: print only the readings BELOW 20 (the low readings).
print("Bug 6:")
sensor_readings = [22, 19, 31, 8, 40]
for r in sensor_readings:
    if r > 20:
        print(r)

# --- Bug 7 ---
# Goal: print a "T-minus" message for every number in the countdown,
# one line per number.
print("Bug 7:")
countdown = [3, 2, 1]
for number in countdown:
    message = f"T-minus {number}"
print(message)
