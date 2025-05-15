**Beatmapr** is a web-based tool that fetches a user's relax scores from the Akatsuki API and matches them against official bancho beatmap packs.  
It visualizes your progress toward full pack completion.

---

## Project Structure

### 🌐 Static Frontend
| File         | Description                                           |
|--------------|-------------------------------------------------------|
| `index.html` | Entry point for the frontend                         |
| `styles.css` | Defines the look and layout of the UI                |
| `script.js`  | Handles all frontend logic and user interaction      |

---

### Backend
| File         | Description                                           |
|--------------|-------------------------------------------------------|
| `server.js`  | Node.js backend — serves static files & runs APIs    |

---

### Python Scripts
| File                    | Description                                                                 |
|-------------------------|-----------------------------------------------------------------------------|
| `get_packs.py`          | Fetches beatmap packs from bancho and writes to `packs.json`               |
| `get_users.py`          | Fetches user data from Akatsuki API and writes to `users.json`             |
| `fetch_ranked_scores.py`| Fetches a user's relax best scores and saves to `{user_id}_scores.txt`     |

---

### Data Files
| File                  | Description                                                                                  |
|-----------------------|--------------------------------------------------------------------------------------------- |
| `packs.json`          | Bancho beatmap packs data `beatmapset_id`, `beatmap_id`, `title`, `difficulty`, `duration`   |
| `users.json`          | Local cache of Akatsuki user data                                                            |
| `{user_id}_scores.txt`| Score file used to check pack progress                                                       |

---

### Node Environment
| File/Folder         | Description                                |
|---------------------|--------------------------------------------|
| `package.json`      | Project metadata and dependencies           |
| `package-lock.json` | Exact version tree of installed packages   |
| `node_modules/`     | Installed npm packages                     |

---

