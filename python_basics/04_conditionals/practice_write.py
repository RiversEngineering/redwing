"""Assignment 4 Practice — Write It From Scratch

For each numbered problem below, the input variable(s) are already given.
Replace "# Write your code here" with your own if / elif / else code
that produces the described output. Nothing is broken here — this file
runs top to bottom without error even before you write anything, since
an unfinished problem is just given variables and a comment.

Concepts practiced
-------------------
- if / else and if / elif / else chains
- comparison operators: == != < > <= >=
- combining conditions with and / or
- the modulo operator % (from Module 2) used inside a condition
- writing a condition from a plain-English description, not just reading one

This script runs on its own, no input() needed: python3 practice_write.py
"""

# --- Problem 1 ---
# Given a battery voltage, print "Charge now" if it's below 11.0,
# otherwise print "OK".
battery_voltage = 10.8
# Write your code here


# --- Problem 2 ---
# Given a test score, print a letter grade:
#   90 or above -> "A"
#   80 or above -> "B"
#   70 or above -> "C"
#   60 or above -> "D"
#   below 60    -> "F"
score = 84
# Write your code here


# --- Problem 3 ---
# Given the speed of a robot's left and right wheel motors, print:
#   "Turning left"     if the right wheel is spinning faster
#   "Turning right"    if the left wheel is spinning faster
#   "Driving straight" if they're equal
left_speed = 40
right_speed = 65
# Write your code here


# --- Problem 4 ---
# Given a temperature, print "Safe operating range" if it's between 32
# and 100 (inclusive of both ends), otherwise print "Warning".
# Use and / or to combine the two boundary checks into one condition.
temperature = 55
# Write your code here


# --- Problem 5 ---
# Given a number, use the % operator to print "Even" or "Odd".
number = 17
# Write your code here


# --- Problem 6 ---
# Given three sensor readings, find and print which one is the largest.
# Do this manually with if / elif / else comparisons — no max().
reading_a = 22
reading_b = 41
reading_c = 17
# Write your code here


# --- Problem 7 ---
# Given two safety flags, print "HALT" if either one is True, otherwise
# print "Continue". Use or.
emergency_stop = False
battery_critical = True
# Write your code here


print("Write It From Scratch complete!")
