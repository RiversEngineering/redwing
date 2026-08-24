"""Assignment 1 Practice — Debug It (Instructor Answer Key)

All six bugs, fixed and uncommented. Compare each fix against the
buggy version in practice_debug.py to see exactly what changed.

    python3 practice_debug_solution.py

Concepts practiced
-------------------
- reading SyntaxError and NameError messages
- matching quotes
- print() syntax
- spotting a logic bug (wrong order) vs. a crash bug
"""

# --- Bug 1 ---
# Fixed: added the missing closing quote.
print("Battery check passed")

# --- Bug 2 ---
# Fixed: added parentheses around the string, as Python 3 requires.
print("Motors connected")

# --- Bug 3 ---
# Fixed: made both quote characters match (double quotes on both ends).
print("Sensors online")

# --- Bug 4 ---
# Fixed: changed Print to lowercase print.
print("Camera ready")

# --- Bug 5 ---
# Fixed: this is a comment now (leading # restored), so Python skips it
# entirely. It correctly prints nothing.
# Check the wiring before powering on.

# --- Bug 6 ---
# Fixed: swapped the order of the two print() calls.
print("Engine check starting...")
print("Engine check complete.")
