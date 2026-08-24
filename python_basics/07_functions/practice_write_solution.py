"""Assignment 7 Practice — Write Your Own Functions (SOLUTION)

Run this file to confirm every function produces the expected output:
python3 practice_write_solution.py
"""

# --- Problem 1 ---
def is_even(n):
    return n % 2 == 0

print(is_even(4))   # expected: True
print(is_even(7))   # expected: False


# --- Problem 2 ---
def celsius_to_fahrenheit(c):
    return c * 9 / 5 + 32

print(celsius_to_fahrenheit(0))     # expected: 32.0
print(celsius_to_fahrenheit(100))   # expected: 212.0
print(celsius_to_fahrenheit(37))    # expected: 98.6


# --- Problem 3 ---
def max_of_three(a, b, c):
    if a >= b and a >= c:
        return a
    elif b >= a and b >= c:
        return b
    else:
        return c

print(max_of_three(3, 7, 5))     # expected: 7
print(max_of_three(10, 2, 9))    # expected: 10
print(max_of_three(-1, -5, -3))  # expected: -1


# --- Problem 4 ---
def count_letter(word, letter):
    count = 0
    for ch in word:
        if ch == letter:
            count = count + 1
    return count

print(count_letter("banana", "a"))       # expected: 3
print(count_letter("mississippi", "s"))  # expected: 4


# --- Problem 5 ---
def average_of_list(numbers):
    total = 0
    for number in numbers:
        total = total + number
    return total / len(numbers)

print(average_of_list([10, 20, 30]))      # expected: 20.0
print(average_of_list([5, 15, 25, 35]))   # expected: 20.0


# --- Problem 6 ---
def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value

print(clamp(150, 0, 100))   # expected: 100
print(clamp(-10, 0, 100))   # expected: 0
print(clamp(50, 0, 100))    # expected: 50


# --- Problem 7 ---
def calculate(a, b, operation):
    if operation == "+":
        return a + b
    elif operation == "-":
        return a - b
    elif operation == "*":
        return a * b
    elif operation == "/":
        return a / b
    else:
        return None

print(calculate(6, 3, "+"))   # expected: 9
print(calculate(6, 3, "-"))   # expected: 3
print(calculate(6, 3, "*"))   # expected: 18
print(calculate(6, 3, "/"))   # expected: 2.0


print("Write practice complete!")
