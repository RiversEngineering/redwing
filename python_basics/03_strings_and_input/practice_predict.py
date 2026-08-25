"""Assignment 3 Practice: Predict the Output

For each numbered snippet below, read the code CAREFULLY before running it,
and write down what you think it will print. Then run the file with
python3 practice_predict.py and check yourself against the real output.

This script does not use input() — everything you need is already in the
code, so it's safe to just read and run.

Concepts practiced
-------------------
- f-strings: f"...{variable}..."
- string concatenation with +
- len() on a string
- converting text to a number with int()
- reasoning about a TypeError without running the code
- a sneak peek at something not yet taught (string repetition with *)
"""

# --- Prediction 1 ---
# My prediction: ____
name = "Ada"
print(f"Hi, {name}!")

# --- Prediction 2 ---
# My prediction: ____
first_word = "Robot"
second_word = "Builder"
print(first_word + " " + second_word)

# --- Prediction 3 ---
# My prediction: ____
print(len("Redwing Robotics"))

# --- Prediction 4 ---
# My prediction: ____
a = 6
b = 7
print(f"{a} times {b} is {a * b}")

# --- Prediction 5 ---
# My prediction: ____
age_text = "16"
age = int(age_text)
print(age + 4)

# --- Prediction 6 ---
# This one is different: predict the ERROR TYPE this line would raise if it
# ran, not a printed value. The line is intentionally left commented out
# below — do NOT uncomment it, it will crash the whole script if you do.
# My prediction (what kind of error?): ____
# print("Power level: " + 100)

# --- Prediction 7 ---
# My prediction: ____
qty = "5"
more = "3"
print(qty + more)

# --- Prediction 8 (Bonus — we haven't taught this, take a guess!) ---
# My prediction: ____
print("-" * 10)

print("Predictions complete! Check your guesses against the real output above.")
