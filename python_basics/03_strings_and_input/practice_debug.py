"""Assignment 3 Practice: Debug It

Seven bugs. Some of them would CRASH the program, so those are left
commented out — read the code and figure out what error they'd raise
and why, without running them. Others are "silent" bugs: the code runs
fine but prints the wrong thing, so those are left LIVE — run the file
and compare the real output to the intended output described in each
comment.

Fix each bug (uncomment + correct the crash-bugs, correct the live
logic-bugs), then run python3 practice_debug.py again to confirm every
line now prints what it was supposed to.

This script does not use input().

Concepts practiced
-------------------
- TypeError from mixing str and int with +
- SyntaxError from a malformed f-string
- NameError from a typo'd variable name
- TypeError from calling len() on a non-string
- silent (non-crashing) bugs caused by forgetting int()/float() conversion
- silent (non-crashing) bugs caused by a missing space in concatenation
"""

# --- Bug 1 ---
# Intended: print "Power level: 100"
# This crashes with a TypeError — + can't join a string and an int.
# print("Power level: " + 100)

# --- Bug 2 ---
# Intended: add 3 to a count of 5 and print 8.
# This crashes with a TypeError — count is still text ("5"), and text
# can't be added to a number with +.
# count = "5"
# total = count + 3
# print(total)

# --- Bug 3 ---
# Intended: add a quantity of 5 and 3 more, printing 8.
# This one does NOT crash — but it doesn't add either. qty and more are
# both strings, so + joins them into the text "53" instead of adding them.
qty = "5"
more = "3"
print(qty + more)

# --- Bug 4 ---
# Intended: print "Hello, Ada!"
# This crashes with a SyntaxError — the f-string is missing its closing
# curly brace after {name.
# name = "Ada"
# print(f"Hello, {name!")

# --- Bug 5 ---
# Intended: print "Robot name: Titan"
# This crashes with a NameError — the variable is robot_name, but the
# print statement typos it as robot_nam.
# robot_name = "Titan"
# print(f"Robot name: {robot_nam}")

# --- Bug 6 ---
# Intended: print how many digits are in the number 42 (should be 2).
# This crashes with a TypeError — len() only works on strings, and 42
# here is an int, not text.
# score = 42
# print(len(score))

# --- Bug 7 ---
# Intended: print "Hello World" (with a space between the two words).
# This does NOT crash, but it's missing the space between first_word and
# second_word, so it prints "HelloWorld" jammed together instead.
first_word = "Hello"
second_word = "World"
print(first_word + second_word)

print("Debugging complete!")
