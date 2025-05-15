# Beatmapr
*to be organised*

Summary : a website that allows you retrieve users relax best scores from akatsuki API and then matches them against bancho ranked beatmap packs to visualise your progress.

# File documentation:

static frontend

• index.html - main entry point for the frontend of the website
• styles.css - defines the visual look
• script.js - frontend logic of the website

backend

• server.js - backend entry point of the website

python scripts

• get_packs.py - a script that retrieves packs from bancho and writes them to packs.json
• get_users.py - a script that retrieves user data from akatsuki api and writes them to users.json
• fetch_ranked_scores.py - a script that retrieves users relax best scores and writes them to a {user_id}_scores.txt file

data

• packs.json - contains beatmapset_id, beatmap_id, title, difficulty, time_duration
• users.json - same format as akatsuki api but stored in a file.
• {user_id}_scores.txt - this file gets compared with packs.json to give you the results.

# others:
• package-lock.json, package.json, node_module - these are node.js related files.
