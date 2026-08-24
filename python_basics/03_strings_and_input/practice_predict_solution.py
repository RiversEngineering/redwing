"""Assignment 3 Practice: Predict the Output (SOLUTION)

Predictions filled in as comments. Run this file to confirm each one.
"""

# --- Prediction 1 ---
# My prediction: Hi, Ada!
name = "Ada"
print(f"Hi, {name}!")

# --- Prediction 2 ---
# My prediction: Robot Builder
first_word = "Robot"
second_word = "Builder"
print(first_word + " " + second_word)

# --- Prediction 3 ---
# My prediction: 16
print(len("Redwing Robotics"))

# --- Prediction 4 ---
# My prediction: 6 times 7 is 42
a = 6
b = 7
print(f"{a} times {b} is {a * b}")

# --- Prediction 5 ---
# My prediction: 20
age_text = "16"
age = int(age_text)
print(age + 4)

# --- Prediction 6 ---
# This one is different: predict the ERROR TYPE this line would raise if it
# ran, not a printed value. The line is intentionally left commented out
# below — do NOT uncomment it, it will crash the whole script if you do.
# My prediction (what kind of error?): TypeError — you can't + a string
# and an int directly. The real message is:
#   TypeError: can only concatenate str (not "int") to str
# print("Power level: " + 100)

# --- Prediction 7 ---
# My prediction: 53  (the text "53", NOT the number 8 — + on two strings
# joins them, it does not add them like numbers)
qty = "5"
more = "3"
print(qty + more)

# --- Prediction 8 (Bonus — we haven't taught this, take a guess!) ---
# My prediction: ----------  (ten dashes — * repeats a string that many times)
print("-" * 10)

print("Predictions complete! Check your guesses against the real output above.")
