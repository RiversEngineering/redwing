"""Assignment 1 Practice — Debug It

Six broken snippets. Five of them would crash the program with an error,
so they're commented out (every line starts with #) — that keeps this
file running cleanly while still showing you exactly what the bug looks
like. Read each one, figure out what's wrong, and think about how you'd
fix it. One bug (Bug 6) does NOT crash — it just produces the wrong
output — so it's left active for you to actually see it run incorrectly.

    python3 practice_debug.py

Concepts practiced
-------------------
- reading SyntaxError and NameError messages
- matching quotes
- print() syntax
- spotting a logic bug (wrong order) vs. a crash bug
"""

# --- Bug 1 ---
# Intended behavior: print the message "Battery check passed"
# Symptom: this crashes with a SyntaxError (unterminated string literal)
# because the closing quote is missing.
# print("Battery check passed)

# --- Bug 2 ---
# Intended behavior: print the message "Motors connected"
# Symptom: this crashes with a SyntaxError (Missing parentheses in call
# to 'print') because Python 3 requires print to be called with parentheses.
# print "Motors connected"

# --- Bug 3 ---
# Intended behavior: print the message "Sensors online"
# Symptom: this crashes with a SyntaxError because the opening quote is a
# double quote (") but the closing quote is a single quote (') — they don't match.
# print("Sensors online')

# --- Bug 4 ---
# Intended behavior: print the message "Camera ready"
# Symptom: this crashes with a NameError (name 'Print' is not defined)
# because Python is case-sensitive — only lowercase print() is a real command.
# Print("Camera ready")

# --- Bug 5 ---
# Intended behavior: this should be a plain comment reminding the team to
# check the wiring before powering on — it should not run as code at all.
# Symptom: as originally written, this line was missing its leading "#":
#     Check the wiring before powering on
# Without the #, Python tries to run those words as a statement and
# crashes with a SyntaxError (invalid syntax).

# --- Bug 6 ---
# Intended behavior: announce "Engine check starting..." first, then
# "Engine check complete." second.
# Symptom: no crash — but the two lines below print in the wrong order.
# This is a logic bug, not a syntax error.
print("Engine check complete.")
print("Engine check starting...")
