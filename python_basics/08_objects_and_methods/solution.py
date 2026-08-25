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
print(len(raw_input))            # 15 — includes the leading/trailing spaces
print(len(raw_input.strip()))    # 9  — whitespace removed, original unchanged

# --- Task 2: list methods that mutate in place ---
fleet = ["scout", "hauler", "sentry"]
fleet.append("drone")
fleet.sort()
print(fleet)   # ['drone', 'hauler', 'scout', 'sentry']

# --- Task 3: bug fix — .append() returns None, not the new list ---
# The old buggy version was:
#   names = fleet.append("medic")
#   print(names)          # prints None!
# .append() mutates fleet IN PLACE and hands back None — it does NOT
# return the updated list. Assigning its result to `names` just gives
# you None. The fix: call .append() on its own line, then print fleet.
fleet.append("medic")
print(fleet)   # ['drone', 'hauler', 'scout', 'sentry', 'medic']

# --- Task 4: attribute vs. method — Python's built-in complex numbers ---
c = 3 + 4j
print(c.real)          # 3.0  — attribute: just data, no parens
print(c.imag)          # 4.0  — attribute: just data, no parens
print(c.conjugate())   # (3-4j) — method: it computes a NEW complex
                       # number and returns it, so it needs ()
# .conjugate() needs () because it performs a calculation (an action)
# and hands back a new value; .real and .imag need no () because they
# are just data already sitting on the object — nothing to "do".

# --- Task 5: reading real robot code (annotation model / answer key) ---
#
# ===== examples/01_drive.py =====
#
# from redwing import Robot   <- imports the Robot class (a blueprint for objects)
# robot = Robot()              <- creates a new Robot OBJECT and stores it in `robot`
# motor = robot.D0.motor()     <- robot.D0 reads an ATTRIBUTE (port D0); .motor()
#                                  is a METHOD call that creates a new motor OBJECT
# robot.start()                 <- calls a METHOD on robot (locks in configuration)
# motor.set_power(50)           <- calls a METHOD on motor (an action: spin at 50%)
# robot.sleep(2)                <- calls a METHOD on robot (an action: pause 2 sec)
# motor.stop()                  <- calls a METHOD on motor (an action: stop spinning)
#
# ===== examples/05_obstacle_avoidance.py =====
#
# from redwing import Robot     <- imports the Robot class (a blueprint for objects)
# robot = Robot()                <- creates a new Robot OBJECT
# left   = robot.D0.motor()      <- robot.D0 is an ATTRIBUTE; .motor() is a METHOD
#                                    call that creates a new motor OBJECT (left)
# right  = robot.D1.motor()      <- same pattern: robot.D1 ATTRIBUTE, .motor() METHOD
#                                    creates another motor OBJECT (right)
# sensor = robot.D2.ultrasonic() <- robot.D2 is an ATTRIBUTE; .ultrasonic() is a
#                                    METHOD call that creates a new sensor OBJECT
# robot.start()                  <- calls a METHOD on robot (locks in configuration)
# d = sensor.distance             <- reads an ATTRIBUTE (no parens!): sensor.distance
#                                    is just data — the current measured distance
# left.set_power(-50)             <- calls a METHOD on left (an action: reverse)
# right.set_power(-50)            <- calls a METHOD on right (an action: reverse)
# robot.sleep(0.5)                 <- calls a METHOD on robot (pause 0.5 sec)
# left.set_power(60)               <- calls a METHOD on left (an action: forward)
# right.set_power(-60)             <- calls a METHOD on right (an action: reverse,
#                                     so the robot turns — left forward, right back)
# robot.sleep(0.4)                  <- calls a METHOD on robot (pause 0.4 sec)
# left.set_power(60)                <- calls a METHOD on left (drive forward)
# right.set_power(60)                <- calls a METHOD on right (drive forward)
# robot.sleep(0.05)                  <- calls a METHOD on robot (short pause, then
#                                       the while True: loop reads sensor.distance
#                                       again)

print("Assignment 8 complete — you're ready for the robot examples!")
