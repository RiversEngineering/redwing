"""Assignment 6 Practice — Predict the Output (SOLUTION)

Same code as practice_predict.py, with each "My prediction" blank filled
in with the correct answer. Run this to double-check your own answers:

    python3 practice_predict_solution.py
"""

# --- Prediction 1 ---
# My prediction: 68, 72, 65, 70 (each on its own line)
print("Prediction 1:")
temps = [68, 72, 65, 70]
for t in temps:
    print(t)

# --- Prediction 2 ---
# My prediction: 0, 1, 2, 3, 4 (five lines — stops before 5)
print("Prediction 2:")
for i in range(5):
    print(i)

# --- Prediction 3 ---
# My prediction: red, then yellow
print("Prediction 3:")
colors = ["red", "green", "blue", "yellow"]
print(colors[0])
print(colors[-1])

# --- Prediction 4 ---
# My prediction: 5
print("Prediction 4:")
crew = ["Alex", "Sam", "Jordan", "Riley", "Morgan"]
print(len(crew))

# --- Prediction 5 ---
# My prediction: 82, 91, 88 (only the scores 80 and above)
print("Prediction 5:")
scores = [55, 82, 91, 40, 76, 88]
for s in scores:
    if s >= 80:
        print(s)

# --- Prediction 6 ---
# My prediction: [0, 2, 4, 6]
print("Prediction 6:")
doubled = []
for i in range(4):
    doubled.append(i * 2)
print(doubled)

# --- Prediction 7 ---
# My prediction: 2, 5, 8 (starts at 2, jumps by 3, stops before 10)
print("Prediction 7:")
for i in range(2, 10, 3):
    print(i)

# --- Prediction 8 (Bonus — we haven't taught this, take a guess!) ---
# My prediction: [20, 30] (items at index 1 up to, not including, index 3)
print("Prediction 8:")
nums = [10, 20, 30, 40, 50]
print(nums[1:3])
