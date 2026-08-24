"""Assignment 5 Practice: Write It Yourself

Seven problems, from scratch, using ONLY while loops — no for, no
lists, no functions (those come in later modules). Given values are
provided for each problem below. Read the plain-English task, then
write your own while loop(s) to compute and print the requested
result(s) — no scaffolding is provided on purpose. Check your output
against the expected output listed in practice_write.html.

As distributed (with nothing written yet), this file runs without
crashing — the unfinished problems just don't print anything yet,
since you haven't written the code there. That's expected.

    python3 practice_write.py

Concepts practiced
-------------------
- the counter pattern
- the accumulator pattern (with and without an if filter)
- break to stop a loop early
- combining a while loop with a running "remaining amount"
- choosing the right comparison so the loop stops at the right time
"""

# --- Problem 1: count to 20 ---
# Print the numbers 1 through 20, one per line.
# Write your code here


# --- Problem 2: sum the even numbers ---
# Add up every EVEN number from 1 to 50 (2, 4, 6, ... 50) using a
# while loop, an if (hint: n % 2 == 0), and an accumulator. Print the
# total with an f-string.
# Write your code here


# --- Problem 3: countdown timer ---
# Count down from start by 5s (25, 20, 15, ...), printing each value,
# then print "Go!" once the countdown reaches 0.
start = 25
# Write your code here


# --- Problem 4: battery drain ---
# Each pass, drain battery by 15 and print the new level. Stop
# (break) once the level drops to 25 or below.
battery = 100
# Write your code here


# --- Problem 5: doubling ---
# Keep doubling value until it exceeds 1000. Count how many doublings
# it took, then print both the count and the final value.
value = 1
# Write your code here


# --- Problem 6: guess the secret number ---
# Starting at guess = 1, increase guess by 1 each pass until it
# matches secret. Print how many attempts it took.
secret = 7
# Write your code here


# --- Problem 7: distance remaining ---
# Each pass, decrease distance_remaining by 10 and print the new
# value. Once it reaches 0 or below, print "Arrived!"
distance_remaining = 50
# Write your code here


print("Writing practice complete!")
