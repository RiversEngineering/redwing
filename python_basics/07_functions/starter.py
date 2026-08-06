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
# TODO 1: write def square(n): that returns n * n.
#         Then call it with a couple of values and print the results:
#         print(square(4)) -> 16
#         print(square(7)) -> 49


# --- Task 2: clamp a motor power (mirrors the real robot library) ---
# This is exactly the kind of safety check that lives inside
# motor.set_power() in the real robot library — it keeps a requested
# power from going past what the hardware can safely handle.
# TODO 2: write def clamp_power(power): that returns power clamped to
#         the range -100 to 100:
#           if power > 100: return 100
#           if power < -100: return -100
#           otherwise: return power unchanged
#         Then call it on 150, -200, and 42, printing each result.
#         Expected: 100, -100, 42


# --- Task 3: two parameters — average two numbers ---
# TODO 3: write def average(a, b): that returns (a + b) / 2.
#         print(average(10, 20)) -> 15.0


# --- Task 4: bug fix — a function that forgets to return ---
# The function below displays the answer with print() but doesn't hand
# it back to the caller, so result ends up as None, and None + 1 crashes.
# TODO 4: uncomment the lines below, then change "print(n * n)" to
#         "return n * n" so the math afterward works.

# def broken_square(n):
#     print(n * n)
#
# result = broken_square(5)
# print(result + 1)


# --- Task 5: scope — predict, then run ---
# Before running, predict: will the final print(power) below show
# 10 or 999? Write your guess as a comment, then run the script.
power = 10

def use_local_power():
    power = 999
    print(power)

use_local_power()
print(power)  # your prediction:

print("Assignment 7 complete!")
