"""Assignment 8 — Objects & Methods

Every value you've used since Assignment 1 — strings, lists, numbers —
has secretly been an **object**: a bundle of data (called attributes)
plus actions it knows how to perform (called methods). This lesson
teaches you to read the dot notation that objects use, so that when you
open a real robot script full of things like `robot.D0.motor()` and
`sensor.distance`, you already know what's going on.

Concepts practiced
-------------------
- object            — a value that bundles data + actions together
- thing.attribute   — reads data off an object (no parentheses)
- thing.method(args)— calls an action the object can perform (always
                       has parentheses, even empty ones: ())
- string methods    — .upper(), .lower(), .strip() return a NEW string
- list methods      — .append(x), .sort() mutate the list IN PLACE and
                       return None (a common trap!)
- attribute vs. method on Python's built-in complex number type

This script runs on its own, no input() needed: python3 starter.py
"""

# --- Given: dot notation basics ---
team_name = "Redwing Robotics"
print(team_name.upper())   # .upper() is a METHOD: dot + parens, does something
print(team_name.lower())   # .lower() is also a method — returns a NEW string
print(len(team_name))      # len(...) is a plain FUNCTION, not a method on
                            # team_name — it doesn't use dot notation

# --- Task 1: .strip() returns a new string, original is unchanged ---
raw_input = "   scout-bot   "
# TODO 1: print len(raw_input) (the length including the spaces), then
#         print len(raw_input.strip()) (the length after stripping the
#         whitespace off both ends). Compare the two numbers.


# --- Task 2: list methods that mutate in place ---
fleet = ["scout", "hauler", "sentry"]
# TODO 2: call fleet.append("drone") to add a new robot to the list,
#         then call fleet.sort() to sort the list alphabetically,
#         then print(fleet).
#         Expected: ['drone', 'hauler', 'scout', 'sentry']


# --- Task 3: bug fix — .append() returns None, not the new list ---
names = fleet.append("medic")
print(names)
# The line above prints None! .append() mutates fleet IN PLACE and
# hands back None — it does NOT return the updated list. Assigning
# its result to `names` just gives you None.
# TODO 3: fix this. Call fleet.append("medic") on its own line (don't
#         assign its result to anything), then print(fleet) to see the
#         real updated list.


# --- Task 4: attribute vs. method — Python's built-in complex numbers ---
c = 3 + 4j
# TODO 4: print(c.real) and print(c.imag) — these are ATTRIBUTES, just
#         data, no parentheses needed.
#         Then print(c.conjugate()) — this is a METHOD, it computes and
#         returns a brand new complex number, so it needs ().
#         Expected: 3.0 then 4.0 then (3-4j)
#         Also add a one-line comment explaining in your own words why
#         .conjugate() needs () but .real does not.


# --- Task 5: reading real robot code (no execution — this is a reading ---
# --- and annotation exercise only; you will not run any robot code) ---
#
# Open examples/01_drive.py in a text editor. For every line that
# creates an object, calls a method, or reads an attribute, copy that
# line below as a comment and write a one-line explanation next to it,
# just like the two worked examples below (copied verbatim from the
# real file):
#
# from redwing import Robot   <- imports the Robot class (a blueprint for objects)
# robot = Robot()              <- creates a new Robot OBJECT and stores it in `robot`
# motor = robot.D0.motor()     <- robot.D0 reads an ATTRIBUTE (port D0); .motor()
#                                  is a METHOD call that creates a new motor OBJECT
#
# TODO 5: continue annotating the rest of 01_drive.py below, then do the
#         same for 05_obstacle_avoidance.py. Look for:
#           - lines that create an object          (Something())
#           - lines that call a method              (thing.method(args))
#           - lines that read an attribute          (thing.attribute, no parens)


print("Assignment 8 complete — you're ready for the robot examples!")
