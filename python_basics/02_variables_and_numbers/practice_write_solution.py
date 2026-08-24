"""Assignment 2 Practice: Write It Yourself

Given values are provided for each problem below. Read the plain-English
task, then write your own code from scratch to compute and print the
requested result(s) — no scaffolding is provided on purpose. Check your
answer against the expected output listed in practice_write.html.

Concepts practiced
-------------------
- variables and arithmetic
- + - * / // % **
- +=
- comma-separated print()
"""

# --- Problem 1 ---
radius = 4
area = 3.14159 * radius ** 2
circumference = 2 * 3.14159 * radius
print("Area:", area)
print("Circumference:", circumference)

# --- Problem 2 ---
total_minutes = 137
hours = total_minutes // 60
leftover_minutes = total_minutes % 60
print("Hours:", hours)
print("Leftover minutes:", leftover_minutes)

# --- Problem 3 ---
price = 19.99
tax_rate = 0.08
total_cost = price + price * tax_rate
print("Total cost:", total_cost)

# --- Problem 4 ---
score1 = 88
score2 = 92
score3 = 79
average = (score1 + score2 + score3) / 3
print("Average score:", average)

# --- Problem 5 ---
celsius = 23
fahrenheit = celsius * 9 / 5 + 32
print("Fahrenheit:", fahrenheit)

# --- Problem 6 ---
speed = 45
time = 2
distance = speed * time
print("Distance:", distance)
speed += 15
new_distance = speed * time
print("New distance:", new_distance)

# --- Problem 7 ---
cost = 12.50
amount_paid = 20
change = amount_paid - cost
print("Change due:", change)
