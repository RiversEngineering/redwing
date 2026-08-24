"""Assignment 6 Practice — Predict the Output

For each numbered snippet below, read the code FIRST and write down what
you think it will print in the "My prediction" comment. Only after you've
written a prediction should you run the file to check yourself:

    python3 practice_predict.py

Concepts covered
-----------------
- for item in a_list:
- for i in range(n):
- indexing: a_list[0], a_list[-1]
- len(a_list)
- for + if filtering
- .append() inside a loop
- range(start, stop, step)
- Bonus: list slicing (not taught yet — just take a guess!)
"""

# --- Prediction 1 ---
# My prediction: ____
print("Prediction 1:")
temps = [68, 72, 65, 70]
for t in temps:
    print(t)

# --- Prediction 2 ---
# My prediction: ____
print("Prediction 2:")
for i in range(5):
    print(i)

# --- Prediction 3 ---
# My prediction: ____
print("Prediction 3:")
colors = ["red", "green", "blue", "yellow"]
print(colors[0])
print(colors[-1])

# --- Prediction 4 ---
# My prediction: ____
print("Prediction 4:")
crew = ["Alex", "Sam", "Jordan", "Riley", "Morgan"]
print(len(crew))

# --- Prediction 5 ---
# My prediction: ____
print("Prediction 5:")
scores = [55, 82, 91, 40, 76, 88]
for s in scores:
    if s >= 80:
        print(s)

# --- Prediction 6 ---
# My prediction: ____
print("Prediction 6:")
doubled = []
for i in range(4):
    doubled.append(i * 2)
print(doubled)

# --- Prediction 7 ---
# My prediction: ____
print("Prediction 7:")
for i in range(2, 10, 3):
    print(i)

# --- Prediction 8 (Bonus — we haven't taught this, take a guess!) ---
# My prediction: ____
print("Prediction 8:")
nums = [10, 20, 30, 40, 50]
print(nums[1:3])
