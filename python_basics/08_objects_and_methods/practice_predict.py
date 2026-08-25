"""Assignment 8 Practice: Predict the Output

For each numbered snippet below, read the code CAREFULLY before running it,
and write down what you think it will print. Then run the file with
python3 practice_predict.py and check yourself against the real output.

This script does not use input() — everything you need is already in the
code, so it's safe to just read and run.

Concepts practiced
-------------------
- string methods that return a NEW string: .upper(), .lower(), .strip()
- len() before/after .strip()
- the .append() "returns None" trap when printed directly
- .sort() mutates a list in place and also returns None
- attribute vs. method on Python's built-in complex number type
  (.real / .imag are attributes, .conjugate() is a method)
- method chaining: calling one method directly on the result of another
- a sneak peek at something not yet taught (.count())
- reasoning about a TypeError without running the code
"""

# --- Prediction 1 ---
# My prediction: ____
callsign = "scout-7"
print(callsign.upper())
print(callsign.lower())

# --- Prediction 2 ---
# My prediction: ____
label = "   drone-unit   "
print(len(label))
print(len(label.strip()))

# --- Prediction 3 ---
# My prediction: ____
readings = [12, 18, 9]
print(readings.append(25))

# --- Prediction 4 ---
# My prediction: ____
crew = ["Priya", "Sam", "Amir"]
crew.sort()
print(crew)
# Note: crew.sort() itself returns None. If you had written
# print(crew.sort()) instead of calling .sort() on its own line, you'd
# see None printed here instead of the sorted list — the same trap as
# .append() in Prediction 3.

# --- Prediction 5 ---
# My prediction (real): ____   My prediction (imag): ____
z = 5 + 12j
print(z.real)
print(z.imag)

# --- Prediction 6 ---
# My prediction: ____
print(z.conjugate())

# --- Prediction 7 ---
# My prediction: ____
print("  Hi  ".strip().upper())

# --- Prediction 8 (Bonus — we haven't taught this, take a guess!) ---
# My prediction: ____
print("redwing".count("i"))

# --- Prediction 9 ---
# This one is different: predict the ERROR TYPE this line would raise if it
# ran, not a printed value. The lines are intentionally left commented out
# below — do NOT uncomment them, they will crash the whole script if you do.
# My prediction (what kind of error?): ____
# z2 = 5 + 12j
# print(z2.real())

print("Predictions complete! Check your guesses against the real output above.")
