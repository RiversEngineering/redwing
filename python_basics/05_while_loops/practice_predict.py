"""Assignment 5 Practice: Predict the Output

For each numbered snippet below, read the code BEFORE you run it, and
fill in the blank on the "My prediction" line with what you think it
will print. THEN run this file with

    python3 practice_predict.py

and compare the real output to your prediction. Every snippet here is
complete, working code — nothing is broken and nothing needs to be
filled in except your prediction.

Concepts practiced
-------------------
- while condition:  — checked before every single pass, including the first
- a loop whose condition is already False the first time it's checked
- the counter pattern and the accumulator pattern
- break inside a while True: loop
- stepping by more than 1 each pass
- boundary conditions: < vs <=
- a flag variable that turns a loop off from the inside (bonus)
"""

# --- Prediction 1 ---
# My prediction: ____
n = 4
while n >= 0:
    print(n)
    n -= 1

print("-" * 20)

# --- Prediction 2 ---
# My prediction: ____
n = 0
while n > 0:
    print(n)
    n -= 1
print("loop finished")

print("-" * 20)

# --- Prediction 3 ---
# My prediction: ____
n = 1
total = 0
while n <= 5:
    total += n
    n += 1
print(total)

print("-" * 20)

# --- Prediction 4 ---
# My prediction: ____
count = 0
while True:
    count += 1
    print(count)
    if count == 3:
        break

print("-" * 20)

# --- Prediction 5 ---
# My prediction: ____
n = 1
while n <= 10:
    print(n)
    n += 2

print("-" * 20)

# --- Prediction 6 ---
# Two separate loops, same starting value, two different operators.
# My prediction (Loop A): ____
# My prediction (Loop B): ____
print("Loop A:")
count = 1
while count <= 3:
    print(count)
    count += 1

print("Loop B:")
count = 1
while count < 3:
    print(count)
    count += 1

print("-" * 20)

# --- Prediction 7 ---
# My prediction: ____
level = 50
step = 0
while level > 0:
    step += 1
    level -= 15
    if level < 10:
        break
print(f"stopped after step {step}, level = {level}")

print("-" * 20)

# --- Prediction 8 (Bonus — we haven't taught this, take a guess!) ---
# My prediction: ____
still_running = True
passes = 0
while still_running:
    passes += 1
    print(f"pass {passes}")
    if passes == 2:
        still_running = False
print("stopped")

print("Predict the Output complete!")
