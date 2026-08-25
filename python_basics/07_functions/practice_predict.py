"""Assignment 7 Practice — Predict the Output

Before running this file, read each numbered snippet below and write
down what you think it will print. Fill in the blank on each
"My prediction:" line with your guess, THEN run the script with
python3 practice_predict.py and compare what actually happened.

Getting a prediction wrong is normal and useful -- it means you found a
gap in your mental model of how functions work, which is exactly what
this exercise is for.

This script runs on its own, no input() needed.
"""

# --- Prediction 1 ---
# A simple function call whose return value gets printed.
# My prediction: ____
def double(n):
    return n * 2

print(double(6))


# --- Prediction 2 ---
# The same function called twice with different arguments.
# My prediction (first call):  ____
# My prediction (second call): ____
def cube(n):
    return n * n * n

print(cube(2))
print(cube(3))


# --- Prediction 3 ---
# This function has NO return statement -- it only prints inside itself.
# My prediction (what shout prints internally): ____
# My prediction (what the OUTER print shows):   ____
def shout(word):
    print(word + "!!!")

print(shout("watch out"))


# --- Prediction 4 ---
# A global variable, and a function that makes its OWN local variable
# with the same name.
# My prediction (printed inside the function): ____
# My prediction (printed by the last line):    ____
score = 100

def reset_score():
    score = 0
    print(score)

reset_score()
print(score)


# --- Prediction 5 ---
# One function calling another function to help build its result.
# My prediction: ____
def add_five(n):
    return n + 5

def double_then_add_five(n):
    doubled = double(n)
    return add_five(doubled)

print(double_then_add_five(10))


# --- Prediction 6 ---
# A default parameter value, used with no argument supplied.
# My prediction: ____
def greet(name="Robot"):
    return f"Hello, {name}!"

print(greet())


# --- Prediction 7 ---
# Both functions are DEFINED first, then called later, interleaved with
# other print() statements. Predict the ORDER the lines print in --
# definitions alone don't run anything until they're called.
# My prediction (order of the 5 lines below): ____
def first_message():
    print("A")

def second_message():
    print("B")

print("start")
first_message()
print("middle")
second_message()
print("end")


# --- Prediction 8 (Bonus — we haven't taught this, take a guess!) ---
# This function has a return INSIDE an if block, and nothing after it.
# What happens when the if-condition is False and the return is never
# reached?
# My prediction: ____
def check_temperature(temp):
    if temp > 100:
        return "too hot"

result = check_temperature(50)
print(result)


print("Predict practice complete!")
