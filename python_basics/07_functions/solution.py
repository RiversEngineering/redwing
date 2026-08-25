"""Assignment 7 — Functions

You've written scripts that run straight top to bottom, one line after
another. As programs grow, you often need the same chunk of logic more
than once — and copy-pasting it everywhere gets messy fast. A
**function** lets you name a chunk of logic once and reuse it anywhere,
as many times as you like. In examples/, things like
`motor.set_power(60)` and `robot.sleep(2)` are functions someone else
already wrote for you. This lesson teaches you to write your own.

Concepts practiced
-------------------
- def name(parameters):  — defines a function (nothing runs yet)
- name(arguments)         — calls the function, running its code
- parameters vs. arguments — placeholder names vs. the real values passed in
- return value            — sends a value back to the caller
- a function with no return gives back None
- local scope — a variable created inside a function stays inside it

This script runs on its own, no input() needed: python3 starter.py
"""

# --- Given: a working function ---
def greet(name):
    print(f"Hello, {name}!")

greet("Ada")
greet("Grace")

# --- Task 1: return a value — square a number ---
def square(n):
    return n * n

print(square(4))
print(square(7))

# --- Task 2: clamp a motor power (mirrors the real robot library) ---
# This is exactly the kind of safety check that lives inside
# motor.set_power() in the real robot library — it keeps a requested
# power from going past what the hardware can safely handle.
def clamp_power(power):
    if power > 100:
        return 100
    if power < -100:
        return -100
    return power

print(clamp_power(150))
print(clamp_power(-200))
print(clamp_power(42))

# --- Task 3: two parameters — average two numbers ---
def average(a, b):
    return (a + b) / 2

print(average(10, 20))

# --- Task 4: bug fix — a function that forgets to return ---
# The fixed function hands the answer back with return instead of just
# displaying it with print(), so result now holds a real number.
def broken_square(n):
    return n * n

result = broken_square(5)
print(result + 1)

# --- Task 5: scope — predict, then run ---
# The final print(power) shows 10, not 999: the power = 999 inside
# use_local_power() is a local variable that only exists inside that
# function. It doesn't touch the outer, module-level power.
power = 10

def use_local_power():
    power = 999
    print(power)

use_local_power()
print(power)  # prediction: 10

print("Assignment 7 complete!")
