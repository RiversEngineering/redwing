"""Assignment 5 Practice: Predict the Output (Instructor Answer Key)

For each numbered snippet below, read the code BEFORE you run it, and
fill in the blank on the "My prediction" line with what you think it
will print. THEN run this file with

    python3 practice_predict_solution.py

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
# My prediction: 4, 3, 2, 1, 0 — each on its own line
n = 4
while n >= 0:
    print(n)
    n -= 1

print("-" * 20)

# --- Prediction 2 ---
# My prediction: nothing prints from the loop — n > 0 is already False
# the first time it's checked, so the block never runs. Only
# "loop finished" prints.
n = 0
while n > 0:
    print(n)
    n -= 1
print("loop finished")

print("-" * 20)

# --- Prediction 3 ---
# My prediction: 15
n = 1
total = 0
while n <= 5:
    total += n
    n += 1
print(total)

print("-" * 20)

# --- Prediction 4 ---
# My prediction: 1, 2, 3 — each on its own line, then the loop breaks
count = 0
while True:
    count += 1
    print(count)
    if count == 3:
        break

print("-" * 20)

# --- Prediction 5 ---
# My prediction: 1, 3, 5, 7, 9
n = 1
while n <= 10:
    print(n)
    n += 2

print("-" * 20)

# --- Prediction 6 ---
# Two separate loops, same starting value, two different operators.
# My prediction (Loop A): 1, 2, 3 — last value printed is 3
# My prediction (Loop B): 1, 2 — last value printed is 2
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
# My prediction: stopped after step 3, level = 5
# (step 1: level 35, step 2: level 20, step 3: level 5 — 5 < 10, so break)
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
# My prediction: pass 1 and pass 2 print, then "stopped" — the flag
# flips to False right after the second pass, so the loop body runs
# exactly twice.
still_running = True
passes = 0
while still_running:
    passes += 1
    print(f"pass {passes}")
    if passes == 2:
        still_running = False
print("stopped")

print("Predict the Output complete!")
