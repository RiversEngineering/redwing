"""Assignment 4 — Making Decisions

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

This script runs on its own, no input() needed: python3 starter.py
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
# TODO 1: add an elif here for distance_cm < 30 that prints "Slow down"
# TODO 1: add an else that prints "Full speed ahead"

# --- Task 2: combine conditions with 'and', store the result ---
battery_voltage = 11.2
# TODO 2: create is_low, a boolean that is True only when
#         battery_voltage < 11.5 AND battery_voltage > 9.0
# TODO 2: then write an if/else on is_low:
#         if is_low, print "Battery low — recharge soon."
#         else, print "Battery OK."

# --- Task 3: fix the indentation bug ---
# The block below won't even run yet — it's commented out because as
# written it raises an IndentationError (the else: body isn't indented
# to match the if: body, and Python needs every line in a block to line
# up exactly). Uncomment the 5 lines below and fix the indentation so
# the if body and else body are each indented consistently.
# motor_temp_c = 45
# if motor_temp_c > 40:
#     print("Motor hot — reduce speed.")
# else:
# print("Motor temperature normal.")

# --- Task 4: combine conditions with 'or', fix the typo ---
emergency_stop = False
battery_critical = True
# TODO 4: write an if/else:
#         if emergency_stop OR battery_critical is True, print "HALTING ALL MOTORS"
#         (note: fix the typo — it should say HALTING, not HALYING)
#         else, print "Systems normal."

# --- Task 5: predict, then run ---
# TODO 5: before running, write your predicted output as a comment
# on the line below.
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
