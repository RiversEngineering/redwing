"""Assignment 2 Practice: Debug It

Seven bugs are hiding below, one per numbered section. Some of them would
crash the program if run, so those are commented out for now — read the
code and the "Intended" comment, and figure out from the error type what
must be wrong before you uncomment and fix it. The rest run live right
now but print the wrong answer; find out why and fix them.

Concepts practiced
-------------------
- reading error messages (NameError, SyntaxError, ZeroDivisionError)
- operator precedence
- variable naming rules
- += placement
- variable reassignment / shadowing mistakes
"""

# --- Bug 1 ---
# Intended: store a robot's test score and print it.
# score = 95
# print(scroe)

# --- Bug 2 ---
# Intended: compute the average of three scores (90, 80, 100) and print it.
a = 90
b = 80
c = 100
average = a + b + c / 3
print("Average:", average)

# --- Bug 3 ---
# Intended: store a robot's finishing place (1st place) and print it.
# 1st_place = 1
# print(1st_place)

# --- Bug 4 ---
# Intended: increase the robot's speed by 10, then print the new speed.
speed = 20
print("Speed:", speed)
speed += 10

# --- Bug 5 ---
# Intended: compute the average of three sensor readings (10, 20, 30) and print it.
# reading_total = 10 + 20 + 30
# reading_count = 0
# average_reading = reading_total / reading_count
# print(average_reading)

# --- Bug 6 ---
# Intended: convert 20 degrees Celsius to Fahrenheit and print it.
celsius = 20
fahrenheit = celsius * 9 / 4 + 32
print("Fahrenheit:", fahrenheit)

# --- Bug 7 ---
# Intended: print the robot's cruising speed, which should still be 30.
cruising_speed = 30
cruising_speed = cruising_speed - 30
print("Cruising speed:", cruising_speed)
