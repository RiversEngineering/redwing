"""Assignment 7 Practice — Debug the Functions

Seven bugs are waiting below, each in its own numbered section.

Bugs 1, 2, 4, and 5 would CRASH the program, so they ship commented
out -- uncomment each block, run the file, read the traceback, then fix
the code so it runs cleanly.

Bugs 3, 6, and 7 do NOT crash -- they run and print a wrong-but-plausible
answer. Those ship live/uncommented. Read the spec comment above each
one, run the file, and fix the logic so the printed result matches the
spec.

Run the file after every change: python3 practice_debug.py
"""

# --- Bug 1: missing return ---
# Intended behavior: compute_area should return width * height so the
# result can be reused in more math later (here, adding a 10 sq. ft.
# safety border). Instead it prints the area but never returns it, so
# total_area ends up trying to add 10 to None.
# Expected error type: TypeError (can't add None and an int)
# Expected output after the fix: 30

# def compute_area(width, height):
#     print(width * height)
#
# total_area = compute_area(5, 4) + 10
# print(total_area)


# --- Bug 2: forgot to call the function ---
# Intended behavior: triple(4) should return 4 * 3 = 12, and result
# should hold that number so more math can be done with it.
# Expected error type: TypeError (you can't do math between a function
# and a number -- don't worry about the exact wording Python prints for
# the function itself, it can look different every run; the important
# part is that math with it fails)
# Expected output after the fix: 17

# def triple(n):
#     return n * 3
#
# result = triple  # bug: missing the (4) -- this grabs the function itself, not a number
# total = result + 5
# print(total)


# --- Bug 3: arguments passed in the wrong order (LIVE bug, no crash) ---
# Intended behavior: a race car has traveled 5 miles of a 20-mile track.
# remaining_distance should be how many miles are LEFT: 20 - 5 = 15.
def subtract(a, b):
    return a - b

remaining_distance = subtract(5, 20)
print(remaining_distance)  # should be 15


# --- Bug 4: dedented line runs at the wrong time ---
# Intended behavior: every time summarize_lap runs, it should report how
# far off the best time a lap was. The print() line below was meant to
# be the last line INSIDE the function, but it isn't indented, so it's
# not part of the function body at all -- it runs immediately, once,
# right when Python reads the def block (before the function is ever
# called), and "difference" doesn't exist yet at that point.
# Expected error type: NameError (name 'difference' is not defined)
# Expected output after the fix: You were 2 seconds off the best time.

# def summarize_lap(lap_time, best_time):
#     difference = lap_time - best_time
# print(f"You were {difference} seconds off the best time.")
#
# summarize_lap(32, 30)


# --- Bug 5: missing a required argument ---
# Intended behavior: average_two should return the average of TWO
# numbers, a and b.
# Expected error type: TypeError: average_two() missing 1 required
# positional argument: 'b'
# Expected output after the fix: 15.0

# def average_two(a, b):
#     return (a + b) / 2
#
# print(average_two(10))


# --- Bug 6: off-by-one boundary check (LIVE bug, no crash) ---
# Spec: a distance of 10 cm or LESS counts as "too close" -- 10 itself
# should count as too close.
def is_too_close(distance_cm):
    if distance_cm < 10:
        return True
    return False

print(is_too_close(5))    # should be True
print(is_too_close(10))   # should be True (boundary case -- currently wrong)
print(is_too_close(15))   # should be False


# --- Bug 7: accumulator reset inside the loop (LIVE bug, no crash) ---
# Intended behavior: sum_range should add up every whole number from 1
# through n and return the total (for n = 5: 1+2+3+4+5 = 15).
def sum_range(n):
    for i in range(1, n + 1):
        total = 0
        total = total + i
    return total

print(sum_range(5))  # should be 15
