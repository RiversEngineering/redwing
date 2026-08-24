"""Assignment 4 Practice — Write It From Scratch (solution)

Concepts practiced
-------------------
- if / else and if / elif / else chains
- comparison operators: == != < > <= >=
- combining conditions with and / or
- the modulo operator % (from Module 2) used inside a condition
- writing a condition from a plain-English description, not just reading one

This script runs on its own, no input() needed: python3 practice_write_solution.py
"""

# --- Problem 1 ---
# Given a battery voltage, print "Charge now" if it's below 11.0,
# otherwise print "OK".
battery_voltage = 10.8
if battery_voltage < 11.0:
    print("Charge now")
else:
    print("OK")

# --- Problem 2 ---
# Given a test score, print a letter grade:
#   90 or above -> "A"
#   80 or above -> "B"
#   70 or above -> "C"
#   60 or above -> "D"
#   below 60    -> "F"
score = 84
if score >= 90:
    print("A")
elif score >= 80:
    print("B")
elif score >= 70:
    print("C")
elif score >= 60:
    print("D")
else:
    print("F")

# --- Problem 3 ---
# Given the speed of a robot's left and right wheel motors, print:
#   "Turning left"     if the right wheel is spinning faster
#   "Turning right"    if the left wheel is spinning faster
#   "Driving straight" if they're equal
left_speed = 40
right_speed = 65
if right_speed > left_speed:
    print("Turning left")
elif left_speed > right_speed:
    print("Turning right")
else:
    print("Driving straight")

# --- Problem 4 ---
# Given a temperature, print "Safe operating range" if it's between 32
# and 100 (inclusive of both ends), otherwise print "Warning".
# Use and / or to combine the two boundary checks into one condition.
temperature = 55
if temperature >= 32 and temperature <= 100:
    print("Safe operating range")
else:
    print("Warning")

# --- Problem 5 ---
# Given a number, use the % operator to print "Even" or "Odd".
number = 17
if number % 2 == 0:
    print("Even")
else:
    print("Odd")

# --- Problem 6 ---
# Given three sensor readings, find and print which one is the largest.
# Do this manually with if / elif / else comparisons — no max().
reading_a = 22
reading_b = 41
reading_c = 17
if reading_a >= reading_b and reading_a >= reading_c:
    print("The largest reading is A:", reading_a)
elif reading_b >= reading_a and reading_b >= reading_c:
    print("The largest reading is B:", reading_b)
else:
    print("The largest reading is C:", reading_c)

# --- Problem 7 ---
# Given two safety flags, print "HALT" if either one is True, otherwise
# print "Continue". Use or.
emergency_stop = False
battery_critical = True
if emergency_stop or battery_critical:
    print("HALT")
else:
    print("Continue")

print("Write It From Scratch complete!")
