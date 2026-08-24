"""Assignment 3 Practice: Write It Yourself (SOLUTION)

One possible correct answer for each problem. Wording can vary — what
matters is that the values match the expected output in
practice_write.html.
"""

# --- Problem 1 ---
team_name = "Redwing Robotics"
print(f"Welcome, {team_name}! Your team name has {len(team_name)} characters.")

# --- Problem 2 ---
first_num = 12
second_num = 7
print(f"Sum: {first_num + second_num}")
print(f"Difference: {first_num - second_num}")
print(f"Product: {first_num * second_num}")

# --- Problem 3 ---
team_name = "Redwing"
robot_number = 3
badge = f"{team_name}-{robot_number}"
print(badge)
print(len(badge))

# --- Problem 4 ---
celsius = 100.0
fahrenheit = celsius * 9 / 5 + 32
print(f"{celsius}°C is {fahrenheit}°F")

# --- Problem 5 ---
hours = 2
minutes = 45
total_minutes = hours * 60 + minutes
print(f"{hours} hours and {minutes} minutes is {total_minutes} minutes total.")

# --- Problem 6 ---
sentence = "Robots are awesome"
print(f"*** {sentence} ***")
print(len(sentence))

# --- Problem 7 ---
noun = "gear"
verb = "spins"
number = 7
print(f"The {noun} {verb} {number * 2} times before breakfast!")

print("Writing practice complete!")
