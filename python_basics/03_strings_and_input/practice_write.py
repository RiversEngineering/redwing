"""Assignment 3 Practice: Write It Yourself

Seven problems. Each one gives you starting variables and asks you to
write a few lines from scratch — no fill-in-the-blank this time. Check
your output against the expected output listed for each problem in
practice_write.html.

This script does not use input() — all starting values are already given
as variables. As distributed (with nothing written yet), this file runs
without crashing; it just won't print much until you fill in each part.

Concepts practiced
-------------------
- f-strings: f"...{variable}..."
- string concatenation with +
- len() on a string
- arithmetic with already-converted numbers
- combining several variables (strings, ints, floats) into one message
"""

# --- Problem 1 ---
# Given team_name, print a welcome sentence with an f-string that also
# includes len(team_name).
team_name = "Redwing Robotics"
# Write your code here

# --- Problem 2 ---
# Given first_num and second_num, print their sum, difference, and
# product, each on its own line with a labeled f-string.
first_num = 12
second_num = 7
# Write your code here

# --- Problem 3 ---
# Given team_name and robot_number, build a "badge" string combining them
# (e.g. "Redwing-3") using concatenation and/or an f-string, print it,
# then print its length with len().
team_name = "Redwing"
robot_number = 3
# Write your code here

# --- Problem 4 ---
# Given celsius, convert it to Fahrenheit (F = C * 9 / 5 + 32) and print
# the result with an f-string.
celsius = 100.0
# Write your code here

# --- Problem 5 ---
# Given hours and minutes, compute the total number of minutes and print
# it with an f-string.
hours = 2
minutes = 45
# Write your code here

# --- Problem 6 ---
# Given sentence, print it wrapped in decoration using an f-string
# (e.g. f"*** {sentence} ***"), then print its length with len().
sentence = "Robots are awesome"
# Write your code here

# --- Problem 7 ---
# Given noun, verb, and number, build and print a silly mad-libs style
# sentence that combines all three plus number * 2, using an f-string.
noun = "gear"
verb = "spins"
number = 7
# Write your code here

print("Writing practice complete!")
