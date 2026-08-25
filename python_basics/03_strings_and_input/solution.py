"""Assignment 3 — Strings & Input (SOLUTION)

Strings are text. In this assignment you'll join strings together, build
cleaner output with f-strings, and use input() to read text the user
types — then convert that text into numbers so you can do math with it.

Concepts practiced
-------------------
- string concatenation with +
- f-strings: f"...{variable}..."
- len() on a string
- input() always returns a string
- converting input with int() / float()

This script uses input(), so run it from a terminal and type your
answers when prompted:  python3 solution.py
"""

# --- Given: a first input() call ---
name = input("What's your name? ")
print(f"Hello, {name}! Let's write some Python.")

# --- Task 1: team name and its length ---
team_name = input("What's your robotics team's name? ")
print(f"{team_name} has {len(team_name)} characters in its name.")

# --- Task 2: convert input to a number before doing math ---
# input() always returns text — convert it with int() before using math on it.
age = int(input("How old are you? "))
age_in_months = age * 12
print(f"You are about {age_in_months} months old.")

# --- Task 3: build a sentence with + ---
first = "Team"
second = "Redwing"
print(first + " " + second)

# --- Task 4: fixed version (f-string instead of + on a number) ---
print(f"Power level: {100}")

# --- Task 5: predict, then run ---
# Predicted output: 6 times 7 is 42
a = 6
b = 7
print(f"{a} times {b} is {a * b}")

print("Assignment 3 complete!")
