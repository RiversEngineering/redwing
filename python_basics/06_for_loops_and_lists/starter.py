"""Assignment 6 — For Loops & Lists

You've repeated code with while loops. Now you'll meet lists — an
ordered collection of values — and the for loop, Python's tool for
running a block of code once per item automatically. Robots deal with
lists constantly: a list of sensor readings, a list of waypoints, a
list of motor speeds.

Concepts practiced
-------------------
- lists: sensor_readings = [22, 19, 31, 8, 40]
- indexing: sensor_readings[0] is the first item, [-1] is the last
- len(a_list) — number of items in a list
- for item in a_list:  — runs the block once per item
- for i in range(n):  — runs the block n times, i goes 0, 1, ..., n-1
- .append(value) — adds an item to the end of a list

This script runs on its own, no input() needed: python3 starter.py
"""

# --- Given: a working for loop over a list ---
sensor_readings = [22, 19, 31, 8, 40]
for reading in sensor_readings:
    print(reading)

# --- Task 1: for + if — print only readings below 20 ---
# TODO 1: loop through sensor_readings and print only the values
#         that are less than 20 (expected: 19, then 8)


# --- Task 2: accumulator over a list — average the readings ---
# TODO 2: use a for loop to add up all the values in sensor_readings
#         into a variable called total, then compute and print the
#         average with an f-string: total / len(sensor_readings)


# --- Task 3: range() — print four motor names ---
# TODO 3: use "for i in range(4):" to print "Motor 0", "Motor 1",
#         "Motor 2", "Motor 3" (one f-string print per line)


# --- Task 4: append — build a list of squares ---
squares = []
# TODO 4: use "for i in range(5):" and append i * i to squares
#         each time through the loop
print(squares)

# --- Task 5: indexing — first and last item ---
# Remember: indices start at 0, so index 0 is the first item.
# TODO 5: print the first reading using index 0
# TODO 5: print the last reading using index -1

print("Assignment 6 complete!")
