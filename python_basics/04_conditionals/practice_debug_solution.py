"""Assignment 4 Practice — Debug It (solution)

All 7 bugs fixed and uncommented.

Concepts practiced
-------------------
- '=' (assignment) vs '==' (comparison)
- the required colon ':' after if / elif / else
- indentation as a real, checked part of Python's syntax
- and vs or — picking the wrong one produces a branch that never fires
- elif ordering — a broad condition checked before a narrow one hides it
- boundary operators: < vs <=
- comparing a string to a number (needs int() first — see Module 3)

This script runs on its own, no input() needed: python3 practice_debug_solution.py
"""

# --- Bug 1 (fixed: '=' -> '==') ---
# Goal: print "Threshold reached" when x is exactly 10.
x = 10
if x == 10:
    print("Threshold reached")

# --- Bug 2 (fixed: added missing colon) ---
# Goal: print "Motor cool" when motor_temp_c is 40 or below.
motor_temp_c = 35
if motor_temp_c <= 40:
    print("Motor cool")

# --- Bug 3 (fixed: else body indented to match the if body) ---
# Goal: print "Sensor error" if reading is negative, otherwise print the
# reading itself.
reading = -5
if reading < 0:
    print("Sensor error")
else:
    print(reading)

# --- Bug 4 (fixed: 'and' -> 'or') ---
# Goal: sound the alarm if the temperature is too low (under 32) OR too
# high (over 100).
temperature = 105
if temperature < 32 or temperature > 100:
    print("ALARM: temperature out of safe range")
else:
    print("Temperature normal")

# --- Bug 5 (fixed: narrow condition checked first) ---
# Goal: give a discount tier based on order_total:
#   under $10  -> "Tiny order discount"
#   under $100 -> "Standard discount"
#   otherwise  -> "No discount"
order_total = 5
if order_total < 10:
    print("Tiny order discount")
elif order_total < 100:
    print("Standard discount")
else:
    print("No discount")

# --- Bug 6 (fixed: '<' -> '<=') ---
# Goal: any speed of 60 or below (that's <= 60) counts as "Safe speed".
speed = 60
if speed <= 60:
    print("Safe speed")
else:
    print("Too fast")

# --- Bug 7 (fixed: convert age_text to int before comparing) ---
# Goal: print "Old enough" if age_text (typed in by a user, so it starts
# out as a string) represents an age of 18 or older.
age_text = "20"
if int(age_text) >= 18:
    print("Old enough")
else:
    print("Not old enough")

print("Debug It complete!")
