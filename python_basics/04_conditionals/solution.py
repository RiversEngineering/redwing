"""Assignment 4 — Making Decisions (solution)

Your code has only run top-to-bottom so far. Now you'll teach it to make
choices: run different code depending on what a variable's value is. This
is exactly how a robot decides "should I stop, slow down, or keep going?"
based on a sensor reading.

Concepts practiced
-------------------
- comparison operators: == != < > <= >=
- booleans: True / False
- if / else
- if / elif / else chains
- combining conditions with and / or
- indentation defines the block — it is not optional in Python

This script runs on its own, no input() needed: python3 solution.py
"""

# --- Given: a working if/else ---
distance_cm = 18
if distance_cm < 20:
    print("Too close! Back up.")
else:
    print("Path is clear.")

# --- Task 1: three-tier decision with elif ---
# A real robot doesn't just have "close" and "clear" — it has tiers.
distance_cm = 8
if distance_cm < 10:
    print("STOP")
elif distance_cm < 30:
    print("Slow down")
else:
    print("Full speed ahead")

# --- Task 2: combine conditions with 'and', store the result ---
battery_voltage = 11.2
is_low = battery_voltage < 11.5 and battery_voltage > 9.0
if is_low:
    print("Battery low — recharge soon.")
else:
    print("Battery OK.")

# --- Task 3: fix the indentation bug ---
# Fixed: the if body and else body are each indented consistently.
motor_temp_c = 45
if motor_temp_c > 40:
    print("Motor hot — reduce speed.")
else:
    print("Motor temperature normal.")

# --- Task 4: combine conditions with 'or', fix the typo ---
emergency_stop = False
battery_critical = True
if emergency_stop or battery_critical:
    print("HALTING ALL MOTORS")
else:
    print("Systems normal.")

# --- Task 5: predict, then run ---
# Predicted output: Zone C  (55 is not < 20, not < 50, but is < 80)
sensor_reading = 55
if sensor_reading < 20:
    print("Zone A")
elif sensor_reading < 50:
    print("Zone B")
elif sensor_reading < 80:
    print("Zone C")
else:
    print("Zone D")

print("Assignment 4 complete!")
