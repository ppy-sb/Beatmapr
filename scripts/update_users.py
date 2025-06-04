import json
import os
import re

# Load users.json from public folder (go up one level from scripts/)
users_path = os.path.join("..", "public", "users.json")
with open(users_path, 'r', encoding='utf-8') as f:
    users = json.load(f)

# Process each user
for user in users:
    score_file_path = os.path.join("..", "data", f"{user['id']}_scores.txt")
    if os.path.exists(score_file_path):
        with open(score_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r"Total scores:\s*([\d.]+)", content)
            if match:
                user['total_scores'] = int(float(match.group(1)))
            else:
                print(f"No 'Total scores' found in {score_file_path}")
    else:
        print(f"File not found: {score_file_path}")

# Write back to public/users.json
with open(users_path, 'w', encoding='utf-8') as f:
    json.dump(users, f, indent=2)

print("users.json updated with total_scores.")
