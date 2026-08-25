"""Assignment 3 Practice: Debug It (SOLUTION)

All seven bugs fixed and live. Run python3 practice_debug_solution.py to
confirm each line now prints the intended output.
"""

# --- Bug 1 (fixed) ---
# Intended: print "Power level: 100"
print(f"Power level: {100}")

# --- Bug 2 (fixed) ---
# Intended: add 3 to a count of 5 and print 8.
count = "5"
total = int(count) + 3
print(total)

# --- Bug 3 (fixed) ---
# Intended: add a quantity of 5 and 3 more, printing 8.
qty = "5"
more = "3"
print(int(qty) + int(more))

# --- Bug 4 (fixed) ---
# Intended: print "Hello, Ada!"
name = "Ada"
print(f"Hello, {name}!")

# --- Bug 5 (fixed) ---
# Intended: print "Robot name: Titan"
robot_name = "Titan"
print(f"Robot name: {robot_name}")

# --- Bug 6 (fixed) ---
# Intended: print how many digits are in the number 42 (should be 2).
score = 42
print(len(str(score)))

# --- Bug 7 (fixed) ---
# Intended: print "Hello World" (with a space between the two words).
first_word = "Hello"
second_word = "World"
print(first_word + " " + second_word)

print("Debugging complete!")
