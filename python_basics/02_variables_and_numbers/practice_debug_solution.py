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

# --- Bug 1 (fixed: the print() call had a typo, "scroe" instead of "score") ---
score = 95
print(score)

# --- Bug 2 (fixed: added parentheses so the addition happens before dividing) ---
a = 90
b = 80
c = 100
average = (a + b + c) / 3
print("Average:", average)

# --- Bug 3 (fixed: variable names can't start with a digit) ---
first_place = 1
print(first_place)

# --- Bug 4 (fixed: moved += above the print so the new value is what prints) ---
speed = 20
speed += 10
print("Speed:", speed)

# --- Bug 5 (fixed: reading_count must be the actual number of readings, not 0) ---
reading_total = 10 + 20 + 30
reading_count = 3
average_reading = reading_total / reading_count
print(average_reading)

# --- Bug 6 (fixed: Fahrenheit conversion uses 9 / 5, not 9 / 4) ---
celsius = 20
fahrenheit = celsius * 9 / 5 + 32
print("Fahrenheit:", fahrenheit)

# --- Bug 7 (fixed: store the checkpoint-stopped speed in its own variable ---
# --- instead of overwriting cruising_speed) ---
cruising_speed = 30
stopped_speed = cruising_speed - 30
print("Cruising speed:", cruising_speed)
