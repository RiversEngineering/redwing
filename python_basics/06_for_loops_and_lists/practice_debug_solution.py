"""Assignment 6 Practice — Debug It (SOLUTION)

All seven bugs fixed and uncommented.

    python3 practice_debug_solution.py
"""

# --- Bug 1 (fixed) ---
# Goal: print the last waypoint in the list (55).
print("Bug 1:")
waypoints = [10, 25, 40, 55]
print(waypoints[-1])

# --- Bug 2 (fixed) ---
# Goal: print each reading in the list, one per line.
print("Bug 2:")
readings = [12, 18, 25, 9]
for reading in readings:
    print(reading)

# --- Bug 3 (fixed) ---
# Goal: build up a list of squares: [1, 4, 9]
print("Bug 3:")
squares = []
squares.append(1)
squares.append(4)
squares.append(9)
print(squares)

# --- Bug 4 (fixed) ---
# Goal: print "Lap 1" through "Lap 5" (five laps total).
print("Bug 4:")
for lap in range(1, 6):
    print(f"Lap {lap}")

# --- Bug 5 (fixed) ---
# Goal: build a list of doubled values: [2, 4, 6]
print("Bug 5:")
doubled = []
for n in [1, 2, 3]:
    doubled.append(n * 2)
print(doubled)

# --- Bug 6 (fixed) ---
# Goal: print only the readings BELOW 20 (the low readings).
print("Bug 6:")
sensor_readings = [22, 19, 31, 8, 40]
for r in sensor_readings:
    if r < 20:
        print(r)

# --- Bug 7 (fixed) ---
# Goal: print a "T-minus" message for every number in the countdown,
# one line per number.
print("Bug 7:")
countdown = [3, 2, 1]
for number in countdown:
    message = f"T-minus {number}"
    print(message)
