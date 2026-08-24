"""Assignment 7 Practice — Write Your Own Functions

Seven problems below, each with a plain-English spec written as a
comment. Replace the "Write your code here" / "pass" placeholder in
each function with real code that returns the right answer.

The test calls below each function are already written for you -- don't
change them. Run the file after every function you finish:
python3 practice_write.py

Right now, every function is just a stub that does nothing (the "pass"
keyword is a placeholder that means "do nothing"), so the file runs
without crashing but prints None everywhere. As you fill in each
function, its print() calls should start showing real, correct values.
"""

# --- Problem 1 ---
# Write is_even(n) that returns True if n is an even number, and False
# if it's odd.
def is_even(n):
    # Write your code here
    pass

print(is_even(4))   # expected: True
print(is_even(7))   # expected: False


# --- Problem 2 ---
# Write celsius_to_fahrenheit(c) that converts a Celsius temperature to
# Fahrenheit and returns it. Formula: F = C * 9 / 5 + 32
def celsius_to_fahrenheit(c):
    # Write your code here
    pass

print(celsius_to_fahrenheit(0))     # expected: 32.0
print(celsius_to_fahrenheit(100))   # expected: 212.0
print(celsius_to_fahrenheit(37))    # expected: 98.6


# --- Problem 3 ---
# Write max_of_three(a, b, c) that returns whichever of the three
# numbers is largest. Do NOT use Python's built-in max() function --
# use if/elif/else comparisons instead.
def max_of_three(a, b, c):
    # Write your code here
    pass

print(max_of_three(3, 7, 5))     # expected: 7
print(max_of_three(10, 2, 9))    # expected: 10
print(max_of_three(-1, -5, -3))  # expected: -1


# --- Problem 4 ---
# Write count_letter(word, letter) that returns how many times letter
# appears inside word. You can loop over the characters of a string the
# same way you loop over a list: for ch in word: -- a string is just a
# sequence of characters, so this is a natural extension of what you
# already know from Module 6.
def count_letter(word, letter):
    # Write your code here
    pass

print(count_letter("banana", "a"))       # expected: 3
print(count_letter("mississippi", "s"))  # expected: 4


# --- Problem 5 ---
# Write average_of_list(numbers) that takes a list of numbers and
# returns their average, using a loop to add them up (don't use the
# built-in sum() function -- add each number to a running total
# yourself, like you did with accumulators in Module 6).
def average_of_list(numbers):
    # Write your code here
    pass

print(average_of_list([10, 20, 30]))      # expected: 20.0
print(average_of_list([5, 15, 25, 35]))   # expected: 20.0


# --- Problem 6 ---
# Write clamp(value, low, high) -- a general-purpose version of the
# clamp_power function from the core lesson. It returns:
#   - low, if value is less than low
#   - high, if value is greater than high
#   - value, unchanged, otherwise
def clamp(value, low, high):
    # Write your code here
    pass

print(clamp(150, 0, 100))   # expected: 100
print(clamp(-10, 0, 100))   # expected: 0
print(clamp(50, 0, 100))    # expected: 50


# --- Problem 7 ---
# Write calculate(a, b, operation) -- a mini calculator. operation is a
# string: "+", "-", "*", or "/". Use if/elif/else to perform the right
# arithmetic on a and b and return the result.
def calculate(a, b, operation):
    # Write your code here
    pass

print(calculate(6, 3, "+"))   # expected: 9
print(calculate(6, 3, "-"))   # expected: 3
print(calculate(6, 3, "*"))   # expected: 18
print(calculate(6, 3, "/"))   # expected: 2.0


print("Write practice complete!")
