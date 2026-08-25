"""Assignment 8 Practice: Write It Yourself (SOLUTION)

One possible correct answer for each problem. Wording can vary — what
matters is that the values match the expected output in
practice_write.html.
"""

# --- Problem 1 ---
raw = "   scout-bot   "
cleaned = raw.strip()
print(cleaned)
print(len(raw))
print(len(cleaned))

# --- Problem 2 ---
log = []
log.append("Launch")
log.append("Ascent")
log.append("Cruise")
log.append("Descent")
log.append("Landing")
log.sort()
print(log)

# --- Problem 3 ---
sentence = "the robot rolled over the rocky road"
print(sentence.count("o"))

# --- Problem 4 ---
message = "The robot moves left."
print(message.replace("left", "right"))

# --- Problem 5 ---
log_line = "distance:42,speed:60,battery:88"
print(log_line.split(","))

# --- Problem 6 ---
team_name = "  Redwing Robotics  "
print(team_name.strip().upper())

# --- Problem 7 (CAPSTONE) ---
sensor_readings = [40, 15, 32, 8, 50]
for reading in sensor_readings:
    if reading < 20:
        command = "STOP - obstacle detected"
    elif reading < 35:
        command = "Slow down"
    else:
        command = "Full speed ahead"
    print(f"Reading: {reading} cm -> {command}")

print("Writing practice complete!")
