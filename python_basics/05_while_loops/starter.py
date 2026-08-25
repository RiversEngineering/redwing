"""Assignment 5 — While Loops

You've written if/else to make a single decision. Now you'll learn to
repeat a block of code automatically, as long as a condition stays True.
This is exactly how a robot's main control loop works: it keeps checking
a sensor, over and over, until something tells it to stop.

Concepts practiced
-------------------
- while condition:  — repeats the indented block while condition is True
- making sure the condition eventually becomes False (no infinite loops!)
- the counter pattern:      i = i + 1  /  i += 1
- the accumulator pattern:  total = total + x
- break — exiting a loop early

This script runs on its own, no input() needed: python3 starter.py
"""

# --- Given: a working while loop (countdown) ---
count = 5
while count > 0:
    print(count)
    count -= 1
print("Liftoff!")

# --- Task 1: print 1 through 10 using a while loop ---
# TODO 1: initialize a counter, write the while loop condition,
#         print it, and increment it so it prints 1, 2, 3, ... 10


# --- Task 2: accumulator — sum the numbers 1 through 20 ---
# TODO 2: use a while loop to add up 1 + 2 + 3 + ... + 20 into a
#         variable called total, then print an f-string like
#         "Total: 210"   (this is the correct answer, self-check!)


# --- Task 3: break — stop the loop early ---
# Scenario: the robot uses 12 fuel per second. Stop the loop as soon
# as fuel drops to 20 or below.
fuel = 100
# TODO 3: write a while loop (while fuel > 0:) whose body:
#           - decreases fuel by 12
#           - prints the current fuel level
#           - breaks out of the loop when fuel <= 20

# --- Task 4: bug fix — this loop never stops! ---
# BUG: this loop never stops! (commented out so it can't run away)
# Uncomment the loop, then add the ONE missing line that fixes it.
# n = 1
# while n <= 5:
#     print(n)

# --- Task 5: predict, then run ---
# Before running this file, predict: how many times will this loop
# print, and what is the LAST number it prints?
x = 2
while x < 20:
    print(x)
    x *= 2

print("Assignment 5 complete!")
