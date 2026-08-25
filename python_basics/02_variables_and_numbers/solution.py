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
wheel_diameter_cm = 6.0
wheel_circumference_cm = 3.14159 * wheel_diameter_cm
print("Wheel circumference:", wheel_circumference_cm, "cm")

# --- Task 2: motor power boost ---
motor_power = 45
boost = 15
print("Power before boost:", motor_power)
motor_power += boost
print("Power after boost:", motor_power)

# --- Task 3: converting seconds to minutes and seconds ---
total_seconds = 125
minutes = total_seconds // 60
seconds = total_seconds % 60
print("That's", minutes, "minute(s) and", seconds, "second(s).")

# --- Task 4: fixed the precedence bug with parentheses ---
a = 10
b = 14
c = 18
# We want the average of a, b, and c
average = (a + b + c) / 3
print("Average sensor reading:", average)

# --- Task 5: predict, then run ---
# 2 ** 5   -> 32     (2 to the power of 5)
# 17 // 4  -> 4      (floor division, drops the remainder)
# 17 % 4   -> 1      (remainder after dividing 17 by 4)
print(2 ** 5)
print(17 // 4)
print(17 % 4)

print("Assignment 2 complete!")
