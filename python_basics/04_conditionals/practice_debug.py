"""Assignment 4 Practice — Debug It

Every one of these 7 numbered blocks is broken in some way. Some of them
crash Python outright (those are commented out so this file can still
run — uncommenting a crash-bug on its own is part of the exercise). The
others run just fine but produce the WRONG answer, which is often more
dangerous on a real robot: a crash is loud, a silent logic bug is not.

How to use this file
---------------------
For each bug: read the goal comment, figure out what's wrong, then fix
it. For the commented-out blocks, uncomment them, fix the bug, and
confirm you understand exactly which error Python was raising and why.

Concepts practiced
-------------------
- '=' (assignment) vs '==' (comparison)
- the required colon ':' after if / elif / else
- indentation as a real, checked part of Python's syntax
- and vs or — picking the wrong one produces a branch that never fires
- elif ordering — a broad condition checked before a narrow one hides it
- boundary operators: < vs <=
- comparing a string to a number (needs int() first — see Module 3)

This script runs on its own, no input() needed: python3 practice_debug.py
As distributed, the crash-bugs below (1, 2, 3, 7) are commented out, so
this file runs top to bottom without error — it just prints the WRONG
things for bugs 4, 5, and 6.
"""

# --- Bug 1 ---
# Goal: print "Threshold reached" when x is exactly 10.
# x = 10
# if x = 10:
#     print("Threshold reached")

# --- Bug 2 ---
# Goal: print "Motor cool" when motor_temp_c is 40 or below.
# motor_temp_c = 35
# if motor_temp_c <= 40
#     print("Motor cool")

# --- Bug 3 ---
# Goal: print "Sensor error" if reading is negative, otherwise print the
# reading itself.
# reading = -5
# if reading < 0:
#     print("Sensor error")
# else:
# print(reading)

# --- Bug 4 ---
# Goal: sound the alarm if the temperature is too low (under 32) OR too
# high (over 100).
temperature = 105
if temperature < 32 and temperature > 100:
    print("ALARM: temperature out of safe range")
else:
    print("Temperature normal")

# --- Bug 5 ---
# Goal: give a discount tier based on order_total:
#   under $10  -> "Tiny order discount"
#   under $100 -> "Standard discount"
#   otherwise  -> "No discount"
order_total = 5
if order_total < 100:
    print("Standard discount")
elif order_total < 10:
    print("Tiny order discount")
else:
    print("No discount")

# --- Bug 6 ---
# Goal: any speed of 60 or below (that's <= 60) counts as "Safe speed".
speed = 60
if speed < 60:
    print("Safe speed")
else:
    print("Too fast")

# --- Bug 7 ---
# Goal: print "Old enough" if age_text (typed in by a user, so it starts
# out as a string) represents an age of 18 or older.
# age_text = "20"
# if age_text >= 18:
#     print("Old enough")
# else:
#     print("Not old enough")

print("Debug It complete!")
