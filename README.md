Beatmapr is a web-based tool that fetches a user's relax scores from the Akatsuki API and matches them against official bancho beatmap packs. It visualizes your progress toward full pack completion with a sleek, interactive UI.

Project Structure
🔹 Static Frontend
File	Description
index.html	Main entry point for the frontend UI
styles.css	Defines the look and feel of the interface
script.js	Handles frontend logic and user interaction

🔹 Backend
File	Description
server.js	Entry point for the Node.js backend. Serves static files, APIs, and runs Python scripts

🔹 Python Scripts
File	Description
get_packs.py	Retrieves beatmap packs from bancho and writes them to packs.json
get_users.py	Retrieves Akatsuki user data and writes them to users.json
fetch_ranked_scores.py	Fetches relax best scores and saves them to {user_id}_scores.txt

🔹 Data Files
File	Description
packs.json	Contains beatmapset_id, beatmap_id, title, difficulty, time_duration
users.json	Local copy of Akatsuki API user data
{user_id}_scores.txt	Generated score file used to match against beatmap packs

🔹 Node Environment
File/Folder	Description
package.json	Project metadata and dependencies
package-lock.json	Exact version tree of installed packages
node_modules/	Installed npm modules

How to Run
Install dependencies:

bash
Copy
Edit
npm install
Start the server:

bash
Copy
Edit
node src/server/server.js
Visit your app at:
http://localhost:3000
