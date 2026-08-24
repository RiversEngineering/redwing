"""Assignment 6 Practice — Write It Yourself (SOLUTION)

    python3 practice_write_solution.py
"""

# --- Problem 1 ---
# Given readings below, print each one doubled, one per line.
readings = [12, 45, 8, 33, 19]
for r in readings:
    print(r * 2)


# --- Problem 2 ---
# Given names below, print each with its position number starting at 1,
# e.g. "1: Ada". Use for i in range(len(names)):
names = ["Ada", "Grace", "Katherine"]
for i in range(len(names)):
    print(f"{i + 1}: {names[i]}")


# --- Problem 3 ---
# Given values below, find and print the maximum value using a loop and
# a "best so far" variable with an if comparison. Do not use max().
values = [14, 82, 3, 47, 65, 21]
best = values[0]
for v in values:
    if v > best:
        best = v
print(best)


# --- Problem 4 ---
# Build a list of squares from 1 to 10 using range() and .append() into
# the empty list below, then print the final list.
squares = []
for i in range(1, 11):
    squares.append(i * i)
print(squares)


# --- Problem 5 ---
# Given distances and threshold below, count and print how many
# distances are above the threshold using a loop + if + counter.
distances = [12, 34, 8, 55, 19, 41]
threshold = 20
count = 0
for d in distances:
    if d > threshold:
        count += 1
print(f"Above threshold: {count}")


# --- Problem 6 ---
# Given crew below, print the list in reverse order using range() with
# a negative step.
crew = ["Alex", "Sam", "Jordan", "Riley"]
for i in range(len(crew) - 1, -1, -1):
    print(crew[i])


# --- Problem 7 ---
# Given the two equal-length lists below, loop through indices with
# range(len(motor_names)) and print paired info like "Left: 60".
motor_names = ["Left", "Right"]
motor_powers = [60, 75]
for i in range(len(motor_names)):
    print(f"{motor_names[i]}: {motor_powers[i]}")
