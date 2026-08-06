"""Assignment 3 — Strings & Input

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
answers when prompted:  python3 starter.py
"""

# --- Given: a first input() call ---
name = input("What's your name? ")
print(f"Hello, {name}! Let's write some Python.")

# --- Task 1: team name and its length ---
team_name = input("What's your robotics team's name? ")
# TODO 1: print an f-string that reports how many characters are in
# team_name, using len(team_name). Example wording:
#   "<team_name> has <N> characters in its name."

# --- Task 2: convert input to a number before doing math ---
# TODO 2: input() always returns text — convert it! Wrap the input(...)
# call below in int(...) so age is a number, not text.
age = input("How old are you? ")
age_in_months = age * 12
print(f"You are about {age_in_months} months old.")

# --- Task 3: build a sentence with + ---
first = "Team"
second = "Redwing"
# TODO 3: print one sentence built with + that joins first and second,
# with a space " " between them. Expected output: Team Redwing

# --- Task 4: fix the bug ---
# The line below crashes with:
#   TypeError: can only concatenate str (not "int") to str
# because + can't join a string and a number directly.
# print("Power level: " + 100)
# TODO 4: replace the line above with a working version using an f-string,
# e.g. print(f"Power level: {100}")

# --- Task 5: predict, then run ---
# TODO 5: before running, write your predicted output as a comment
# on the line below.
a = 6
b = 7
print(f"{a} times {b} is {a * b}")

print("Assignment 3 complete!")
