"""Assignment 2 — Variables & Numbers

Variables let a program remember values and reuse them. You'll create
variables, do arithmetic on them, and fix a couple of common bugs.

Concepts practiced
-------------------
- variables and assignment (=)
- int vs float
- arithmetic operators: + - * / // % **
- operator precedence and parentheses
- updating a variable: x = x + 1 and x += 1
"""

# --- Given: battery voltage from 3 cells in series ---
battery_cells = 3
cell_voltage = 3.7
battery_voltage = battery_cells * cell_voltage
print("Battery voltage:", battery_voltage, "V")

# --- Task 1: wheel circumference ---
# Create wheel_diameter_cm = 6.0
# Then compute wheel_circumference_cm = 3.14159 * wheel_diameter_cm
# Then print it with: print("Wheel circumference:", wheel_circumference_cm, "cm")
# TODO 1: write your two lines (and the print) below this comment

# --- Task 2: motor power boost ---
motor_power = 45
boost = 15
print("Power before boost:", motor_power)
# TODO 2: use += to add boost onto motor_power
print("Power after boost:", motor_power)

# --- Task 3: converting seconds to minutes and seconds ---
total_seconds = 125
# TODO 3: create minutes = total_seconds // 60
# TODO 3: create seconds = total_seconds % 60
# Uncomment the line below once both variables above exist
# print("That's", minutes, "minute(s) and", seconds, "second(s).")

# --- Task 4: fix the precedence bug ---
a = 10
b = 14
c = 18
# We want the average of a, b, and c
average = a + b + c / 3   # TODO 4: add parentheses so this computes correctly
print("Average sensor reading:", average)

# --- Task 5: predict, then run ---
# TODO 5: before running, write your predicted output as a comment
# next to each print() call below. Then run the script and check.
print(2 ** 5)
print(17 // 4)
print(17 % 4)

print("Assignment 2 complete!")
