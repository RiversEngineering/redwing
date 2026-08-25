"""Assignment 4 Practice — Predict the Output

Reading code and predicting what it will print — WITHOUT running it — is
one of the most useful skills you can build. It's exactly what you'll do
when you're staring at robot code trying to figure out why it drove the
wrong way.

How to use this file
---------------------
For each numbered block below:
  1. Read the code carefully.
  2. Write your guess on the "# My prediction: ____" line.
  3. THEN run the script (python3 practice_predict.py) and compare.

Every block here is complete, working code — nothing is broken and
nothing needs to be filled in except your prediction.

Concepts practiced
-------------------
- comparison operators: == != < > <= >=
- booleans: True / False
- if / else and if / elif / else chains
- combining conditions with and / or / not
- top-to-bottom, stop-at-first-match elif behavior
- boundary conditions (< vs <=)

This script runs on its own, no input() needed: python3 practice_predict.py
"""

# --- Prediction 1 ---
# My prediction: ____
temperature = 95
if temperature > 90:
    print("Too hot")
else:
    print("Temperature OK")

# --- Prediction 2 ---
# My prediction: ____
speed = 45
if speed < 20:
    print("Slow")
elif speed < 60:
    print("Medium")
else:
    print("Fast")

# --- Prediction 3 ---
# My prediction: ____
light_level = 30
is_daytime = light_level > 20 and light_level < 100
print(is_daytime)
if is_daytime:
    print("Cameras: normal mode")
else:
    print("Cameras: night mode")

# --- Prediction 4 ---
# My prediction: ____
button_a_pressed = False
button_b_pressed = True
should_move = button_a_pressed or button_b_pressed
print(should_move)
if should_move:
    print("Motors: engaged")
else:
    print("Motors: idle")

# --- Prediction 5 ---
# My prediction: ____
print(not True)

# --- Prediction 6 ---
# My prediction: ____
# Careful — more than one of these conditions could be true for this
# score if you checked them on their own. Python doesn't check them on
# their own, though.
score = 95
if score >= 60:
    print("Pass")
elif score >= 90:
    print("Honors")
else:
    print("Fail")

# --- Prediction 7 ---
# Two separate snippets, same starting value, two different operators.
# My prediction (Snippet A): ____
# My prediction (Snippet B): ____
distance_cm = 20

# Snippet A
if distance_cm < 20:
    print("A: Too close")
else:
    print("A: Clear")

# Snippet B
if distance_cm <= 20:
    print("B: Too close")
else:
    print("B: Clear")

# --- Prediction 8 (Bonus — we haven't taught this, take a guess!) ---
# My prediction: ____
x = 5
print(1 < x < 10)

print("Predict the Output complete!")
