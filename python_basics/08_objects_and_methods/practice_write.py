"""Assignment 8 Practice: Write It Yourself

Seven problems. Each one gives you starting variables and asks you to
write a few lines from scratch — no fill-in-the-blank this time. Check
your output against the expected output listed for each problem in
practice_write.html.

This script does not use input() — all starting values are already given
as variables. As distributed (with nothing written yet), this file runs
without crashing; it just won't print much until you fill in each part.

Concepts practiced
-------------------
- .strip() and len() together
- .append() (called 5 times) followed by .sort()
- .count() — new but intuitive: counts how many times something appears
- .replace() — new but intuitive: swaps old text for new text in a string
- .split(",") — new, stretch goal: breaks a string into a list of pieces
- chaining .strip() and .upper() together in one line
- capstone: for + if/elif/else together, simulating a robot's decisions
"""

# --- Problem 1 ---
# Given raw, clean it up with .strip(), then print the cleaned result and
# its len() before and after stripping.
raw = "   scout-bot   "
# Write your code here

# --- Problem 2 ---
# Given the empty list log, append these 5 mission-log strings ONE AT A
# TIME, in this order: "Launch", "Ascent", "Cruise", "Descent", "Landing".
# Then call log.sort() and print(log).
log = []
# Write your code here

# --- Problem 3 ---
# Given sentence, count how many times the letter "o" appears using
# sentence.count("o"), and print the count.
sentence = "the robot rolled over the rocky road"
# Write your code here

# --- Problem 4 ---
# Given message, use .replace() to change "left" to "right", and print
# the corrected sentence.
message = "The robot moves left."
# Write your code here

# --- Problem 5 ---
# Given log_line, use .split(",") to break it into a list of 3 pieces,
# and print the resulting list.
log_line = "distance:42,speed:60,battery:88"
# Write your code here

# --- Problem 6 ---
# Given team_name, chain .strip() and .upper() together in ONE line to
# produce a clean, uppercase, whitespace-free version, and print it.
team_name = "  Redwing Robotics  "
# Write your code here

# --- Problem 7 (CAPSTONE) ---
# Given sensor_readings, loop through it with a for loop. For each
# reading, use if/elif/else to decide and print a simulated motor
# command:
#   reading < 20             -> "STOP - obstacle detected"
#   20 <= reading < 35        -> "Slow down"
#   reading >= 35              -> "Full speed ahead"
# Print each line as: f"Reading: {reading} cm -> {command}"
sensor_readings = [40, 15, 32, 8, 50]
# Write your code here

print("Writing practice complete!")
