"""Assignment 8 Practice: Predict the Output (SOLUTION)

Predictions filled in as comments. Run this file to confirm each one.
"""

# --- Prediction 1 ---
# My prediction: SCOUT-7  then  scout-7
callsign = "scout-7"
print(callsign.upper())
print(callsign.lower())

# --- Prediction 2 ---
# My prediction: 16  then  10  -- wait, count carefully: "   drone-unit   "
# has 3 spaces + "drone-unit" (10 chars) + 3 spaces = 16, and stripped it's
# just "drone-unit" = 10 characters.
label = "   drone-unit   "
print(len(label))
print(len(label.strip()))

# --- Prediction 3 ---
# My prediction: None  -- .append() mutates readings in place but hands
# back None, so printing its return value directly prints None, not the
# updated list.
readings = [12, 18, 9]
print(readings.append(25))

# --- Prediction 4 ---
# My prediction: ['Amir', 'Priya', 'Sam']
crew = ["Priya", "Sam", "Amir"]
crew.sort()
print(crew)
# Note: crew.sort() itself returns None. If you had written
# print(crew.sort()) instead of calling .sort() on its own line, you'd
# see None printed here instead of the sorted list — the same trap as
# .append() in Prediction 3.

# --- Prediction 5 ---
# My prediction (real): 5.0   My prediction (imag): 12.0
z = 5 + 12j
print(z.real)
print(z.imag)

# --- Prediction 6 ---
# My prediction: (5-12j)
print(z.conjugate())

# --- Prediction 7 ---
# My prediction: HI  -- .strip() runs first, removing the outer spaces and
# returning "Hi", then .upper() runs on THAT result, returning "HI".
print("  Hi  ".strip().upper())

# --- Prediction 8 (Bonus — we haven't taught this, take a guess!) ---
# My prediction: 1  -- "redwing" has exactly one "i".
print("redwing".count("i"))

# --- Prediction 9 ---
# This one is different: predict the ERROR TYPE this line would raise if it
# ran, not a printed value. The lines are intentionally left commented out
# below — do NOT uncomment them, they will crash the whole script if you do.
# My prediction (what kind of error?): TypeError -- z2.real is an
# ATTRIBUTE, just a plain float value (12.0-style number) already sitting
# on the object. Putting () after it tries to CALL that float like a
# function, which floats don't support. The real message is:
#   TypeError: 'float' object is not callable
# z2 = 5 + 12j
# print(z2.real())

print("Predictions complete! Check your guesses against the real output above.")
