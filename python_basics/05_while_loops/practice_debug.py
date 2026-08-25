"""Assignment 5 Practice: Debug It

Seven bugs are hiding below, one per numbered section. Three of them
would either hang forever (an infinite loop) or crash the program, so
those are commented out for now — read the code and the "Intended"
comment, and figure out from the description what must be wrong before
you uncomment and fix it. The other four bugs run live right now: they
don't crash or hang, but they produce the wrong output. Find out why
and fix them.

    python3 practice_debug.py

If you ever DO end up running an infinite loop by accident (for
example, while testing your own fix), press Ctrl+C in the terminal to
force-stop it — that always works and it's always safe to use.

Concepts practiced
-------------------
- recognizing an infinite loop before you ever run it
- comparison direction: while x > 0: vs while x < 0:
- break placement — indentation decides what it's conditional on
- initializing an accumulator before the loop starts
- off-by-one errors from < vs <=
- typos that update the wrong variable, leaving the real counter frozen
- operator precedence inside a loop body
"""

# --- Bug 1 ---
# Intended: count up from 1 to 5, printing each number.
# Commented out — this would run forever. n is never changed inside
# the loop, so "n <= 5" stays True on every single pass.
# n = 1
# while n <= 5:
#     print(n)

# --- Bug 2 ---
# Intended: count down from 5 to 1, printing each number.
count = 5
while count < 0:
    print(count)
    count -= 1
print("countdown done")

# --- Bug 3 ---
# Intended: check the level every pass, printing "checking..." each
# time, and stop only once the level has dropped to 50 or below.
level = 100
while level > 0:
    print("checking...", level)
    level -= 10
    if level <= 50:
        print("low enough, stopping")
    break
print("done")

# --- Bug 4 ---
# Intended: sum the numbers 1 through 5 into total, then print it.
# Commented out — this would crash with a NameError. total is used
# inside the loop (total += n) but it's never created first.
# n = 1
# while n <= 5:
#     total += n
#     n += 1
# print(total)

# --- Bug 5 ---
# Intended: print the numbers 1 through 10 (ten lines).
i = 1
while i < 10:
    print(i)
    i += 1

# --- Bug 6 ---
# Intended: count up from 1 to 5, printing each number.
# Commented out — this would run forever. The increment line updates
# "count" instead of the real loop counter, cnt, so cnt never
# changes and "cnt <= 5" stays True forever.
# cnt = 1
# while cnt <= 5:
#     print(cnt)
#     count = cnt + 1

# --- Bug 7 ---
# Intended: each pass, print the robot's total thrust, calculated as
# (speed + boost) * 2, as speed increases by 5 each pass.
speed = 10
boost = 5
seconds = 0
while seconds < 3:
    thrust = speed + boost * 2
    print(f"second {seconds}: thrust = {thrust}")
    speed += 5
    seconds += 1

print("Debugging complete!")
