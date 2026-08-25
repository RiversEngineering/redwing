"""Assignment 8 Practice: Debug It

Seven bugs. Some of them would CRASH the program, so those are left
commented out — read the code and figure out what error they'd raise and
why, without running them. Others are "silent" bugs: the code runs fine
but prints something odd or wrong, so those are left LIVE — run the file
and compare the real output to the intended output described in each
comment.

Fix each bug (uncomment + correct the crash-bugs, correct the live
logic-bugs), then run python3 practice_debug.py again to confirm every
line now prints what it was supposed to.

This script does not use input().

Concepts practiced
-------------------
- the .append() "returns None" trap when its result is captured
- calling a method without () — it doesn't crash, it just isn't "called"
- TypeError from calling an attribute (like .real) as if it were a method
- AttributeError from a typo'd method name
- AttributeError from calling a list-only (or string-only) method on the
  wrong type
- TypeError from .sort()-ing a list of mixed, uncomparable types
- forgetting () on a method call used inside an f-string
"""

# --- Bug 1 ---
# Intended: add "wheel" to inventory, then print the UPDATED list.
# This does NOT crash — but `updated` is not the new list. inventory.append()
# mutates inventory in place and hands back None, so `updated` is just None.
inventory = ["battery", "chassis"]
updated = inventory.append("wheel")
print(updated)

# --- Bug 2 ---
# Intended: print the robot's name in uppercase: TITAN
# This does NOT crash — but .upper is used with no parentheses, so it's
# never actually called. Instead of the uppercase text, Python prints a
# description of the method itself (something like
# "<built-in method upper of str object at 0x...>").
robot_name = "titan"
print(robot_name.upper)

# --- Bug 3 ---
# Intended: print the real part of c: 2.0
# This crashes with a TypeError. c.real is an ATTRIBUTE (a plain number
# already sitting on the object) — putting () after it tries to CALL that
# number like a function, which numbers don't support.
# c = 2 + 9j
# print(c.real())

# --- Bug 4 ---
# Intended: print the word in uppercase: ROBOT
# This crashes with an AttributeError — the method is called .upper(),
# but this line typos it as .uppr().
# word = "robot"
# print(word.uppr())

# --- Bug 5 ---
# Intended: add an exclamation mark onto the end of the message.
# This crashes with an AttributeError — .append() is a LIST method. It
# does not exist on strings (strings are immutable; you can't add onto
# one in place at all).
# message = "hello"
# message.append("!")

# --- Bug 6 ---
# Intended: sort a list of priority numbers: 3, 2, 1 -> 1, 2, 3
# This crashes with a TypeError — "two" snuck in as text instead of the
# number 2, and Python can't compare a string to an int to decide sort
# order.
# mixed = [3, "two", 1]
# mixed.sort()

# --- Bug 7 ---
# Intended: print "Pilot: MARIA"
# This does NOT crash — but {pilot.upper} inside the f-string is missing
# its parentheses, so .upper is never called. Instead of the uppercase
# name, the sentence embeds a description of the method itself (something
# like "Pilot: <built-in method upper of str object at 0x...>").
pilot = "maria"
print(f"Pilot: {pilot.upper}")

print("Debugging complete!")
