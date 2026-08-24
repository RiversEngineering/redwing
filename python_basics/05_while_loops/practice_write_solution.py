"""Assignment 5 Practice: Write It Yourself (Instructor Answer Key)

One completed solution for each of the seven problems in
practice_write.py. Run this file to confirm what the correct output
should look like.

    python3 practice_write_solution.py

Concepts practiced
-------------------
- the counter pattern
- the accumulator pattern (with and without an if filter)
- break to stop a loop early
- combining a while loop with a running "remaining amount"
- choosing the right comparison so the loop stops at the right time
"""

# --- Problem 1: count to 20 ---
i = 1
while i <= 20:
    print(i)
    i += 1

# --- Problem 2: sum the even numbers ---
n = 1
total = 0
while n <= 50:
    if n % 2 == 0:
        total += n
    n += 1
print(f"Total: {total}")

# --- Problem 3: countdown timer ---
start = 25
while start > 0:
    print(start)
    start -= 5
print("Go!")

# --- Problem 4: battery drain ---
battery = 100
while battery > 0:
    battery -= 15
    print(battery)
    if battery <= 25:
        break

# --- Problem 5: doubling ---
value = 1
doublings = 0
while value <= 1000:
    value *= 2
    doublings += 1
print(f"Doublings: {doublings}")
print(f"Final value: {value}")

# --- Problem 6: guess the secret number ---
secret = 7
guess = 1
attempts = 1
while guess != secret:
    guess += 1
    attempts += 1
print(f"Attempts: {attempts}")

# --- Problem 7: distance remaining ---
distance_remaining = 50
while distance_remaining > 0:
    distance_remaining -= 10
    print(distance_remaining)
print("Arrived!")

print("Writing practice complete!")
