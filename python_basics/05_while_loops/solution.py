"""Assignment 5 — While Loops (SOLUTION)

Instructor reference. See starter.py for the student-facing version
with TODOs.

Concepts practiced
-------------------
- while condition:  — repeats the indented block while condition is True
- making sure the condition eventually becomes False (no infinite loops!)
- the counter pattern:      i = i + 1  /  i += 1
- the accumulator pattern:  total = total + x
- break — exiting a loop early
"""

# --- Given: a working while loop (countdown) ---
count = 5
while count > 0:
    print(count)
    count -= 1
print("Liftoff!")

# --- Task 1: print 1 through 10 using a while loop ---
i = 1
while i <= 10:
    print(i)
    i += 1

# --- Task 2: accumulator — sum the numbers 1 through 20 ---
n = 1
total = 0
while n <= 20:
    total = total + n
    n += 1
print(f"Total: {total}")

# --- Task 3: break — stop the loop early ---
# Scenario: the robot uses 12 fuel per second. Stop the loop as soon
# as fuel drops to 20 or below.
fuel = 100
while fuel > 0:
    fuel -= 12
    print(fuel)
    if fuel <= 20:
        break

# --- Task 4: bug fix — this loop never stops! ---
# Fixed: the loop was missing the line that updates n, so the
# condition n <= 5 never became False. Adding n += 1 fixes it.
n = 1
while n <= 5:
    print(n)
    n += 1

# --- Task 5: predict, then run ---
# Prediction: prints 2, 4, 8, 16 (4 times), then x becomes 32 and
# the loop stops because 32 < 20 is False. Last printed value: 16.
x = 2
while x < 20:
    print(x)
    x *= 2

print("Assignment 5 complete!")
