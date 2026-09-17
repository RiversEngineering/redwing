"""Assignment 1 Practice — Debug It

Six broken snippets. Five of them would crash the program with an error.
Read each one, figure out what's wrong, and think about how you'd
fix it. One bug (Bug 6) does NOT crash — it just produces the wrong
output — so it's left active for you to actually see it run incorrectly.

Concepts practiced
-------------------
- reading SyntaxError and NameError messages
- matching quotes
- print() syntax
- spotting a logic bug (wrong order) vs. a crash bug
"""

# --- Bug 1 ---
# Intended behavior: print the message "Battery check passed"
print("Battery check passed)

# --- Bug 2 ---
# Intended behavior: print the message "Motors connected"
print "Motors connected"

# --- Bug 3 ---
# Intended behavior: print the message "Sensors online"
print("Sensors online')

# --- Bug 4 ---
# Intended behavior: print the message "Camera ready"
Print("Camera ready")

# --- Bug 5 ---
# Intended behavior: this should be a plain comment reminding the team to
# check the wiring before powering on — it should not run as code at all.
Check the wiring before powering on

# --- Bug 6 ---
# Intended behavior: announce "Engine check starting..." first, then
# "Engine check complete." second.
print("Engine check complete.")
print("Engine check starting...")
