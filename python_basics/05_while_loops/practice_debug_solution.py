"""Assignment 5 Practice: Debug It (Instructor Answer Key)

Every bug from practice_debug.py is fixed and uncommented below. Run
this file to confirm what the correct output should look like.

    python3 practice_debug_solution.py

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

# --- Bug 1 (fixed: added n += 1, so n eventually reaches 6 and stops) ---
n = 1
while n <= 5:
    print(n)
    n += 1

# --- Bug 2 (fixed: counting down needs count > 0, not count < 0) ---
count = 5
while count > 0:
    print(count)
    count -= 1
print("countdown done")

# --- Bug 3 (fixed: break moved inside the if, so it only fires once
# the level actually drops low enough, instead of after every pass) ---
level = 100
while level > 0:
    print("checking...", level)
    level -= 10
    if level <= 50:
        print("low enough, stopping")
        break
print("done")

# --- Bug 4 (fixed: total = 0 initializes the accumulator before the loop) ---
n = 1
total = 0
while n <= 5:
    total += n
    n += 1
print(total)

# --- Bug 5 (fixed: i <= 10 so the loop runs all ten times) ---
i = 1
while i <= 10:
    print(i)
    i += 1

# --- Bug 6 (fixed: the increment line now updates cnt, the real counter) ---
cnt = 1
while cnt <= 5:
    print(cnt)
    cnt = cnt + 1

# --- Bug 7 (fixed: parentheses make the addition happen before the *2) ---
speed = 10
boost = 5
seconds = 0
while seconds < 3:
    thrust = (speed + boost) * 2
    print(f"second {seconds}: thrust = {thrust}")
    speed += 5
    seconds += 1

print("Debugging complete!")
