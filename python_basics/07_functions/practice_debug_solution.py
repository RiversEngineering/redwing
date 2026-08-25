"""Assignment 7 Practice — Debug the Functions (SOLUTION)

All seven bugs fixed. Run this file to confirm every fix works:
python3 practice_debug_solution.py
"""

# --- Bug 1: missing return (FIXED) ---
# compute_area now returns width * height instead of just printing it,
# so total_area can safely add 10 to a real number.
def compute_area(width, height):
    return width * height

total_area = compute_area(5, 4) + 10
print(total_area)


# --- Bug 2: forgot to call the function (FIXED) ---
# result now holds the return value of triple(4), a number, instead of
# the function itself.
def triple(n):
    return n * 3

result = triple(4)
total = result + 5
print(total)


# --- Bug 3: arguments passed in the wrong order (FIXED) ---
# subtract(20, 5) puts the total distance first and the distance
# traveled second, matching the order subtract(a, b) expects: a - b.
def subtract(a, b):
    return a - b

remaining_distance = subtract(20, 5)
print(remaining_distance)


# --- Bug 4: dedented line runs at the wrong time (FIXED) ---
# The print() line is now indented as part of the function body, so it
# runs each time summarize_lap is called (using that call's own
# "difference"), instead of running once immediately at definition time.
def summarize_lap(lap_time, best_time):
    difference = lap_time - best_time
    print(f"You were {difference} seconds off the best time.")

summarize_lap(32, 30)


# --- Bug 5: missing a required argument (FIXED) ---
# The call site now passes both required arguments.
def average_two(a, b):
    return (a + b) / 2

print(average_two(10, 20))


# --- Bug 6: off-by-one boundary check (FIXED) ---
# Changed "<" to "<=" so a distance of exactly 10 correctly counts as
# too close, matching the spec.
def is_too_close(distance_cm):
    if distance_cm <= 10:
        return True
    return False

print(is_too_close(5))
print(is_too_close(10))
print(is_too_close(15))


# --- Bug 7: accumulator reset inside the loop (FIXED) ---
# total = 0 now runs ONCE, before the loop starts, instead of being
# reset back to 0 on every single iteration.
def sum_range(n):
    total = 0
    for i in range(1, n + 1):
        total = total + i
    return total

print(sum_range(5))
