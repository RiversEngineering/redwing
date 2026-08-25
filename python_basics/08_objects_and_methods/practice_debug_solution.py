"""Assignment 8 Practice: Debug It (SOLUTION)

All seven bugs fixed and live. Run python3 practice_debug_solution.py to
confirm each line now prints the intended output.
"""

# --- Bug 1 (fixed) ---
# Intended: add "wheel" to inventory, then print the UPDATED list.
# Call .append() on its own line (don't capture its return value), then
# print inventory itself.
inventory = ["battery", "chassis"]
inventory.append("wheel")
print(inventory)

# --- Bug 2 (fixed) ---
# Intended: print the robot's name in uppercase: TITAN
robot_name = "titan"
print(robot_name.upper())

# --- Bug 3 (fixed) ---
# Intended: print the real part of c: 2.0
# .real is an ATTRIBUTE, not a method — no parentheses needed (or allowed).
c = 2 + 9j
print(c.real)

# --- Bug 4 (fixed) ---
# Intended: print the word in uppercase: ROBOT
word = "robot"
print(word.upper())

# --- Bug 5 (fixed) ---
# Intended: add an exclamation mark onto the end of the message.
# Strings don't have .append() — build a new string instead and reassign it.
message = "hello"
message = message + "!"
print(message)

# --- Bug 6 (fixed) ---
# Intended: sort a list of priority numbers: 3, 2, 1 -> 1, 2, 3
mixed = [3, 2, 1]
mixed.sort()
print(mixed)

# --- Bug 7 (fixed) ---
# Intended: print "Pilot: MARIA"
pilot = "maria"
print(f"Pilot: {pilot.upper()}")

print("Debugging complete!")
