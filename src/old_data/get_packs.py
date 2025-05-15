from datetime import datetime
import ossapi
import json
import time
import os
import re

# Your client credentials
CLIENT_ID = 31586
API_KEY = "Sty09gmsufGNjadWZyhNftashebxHV7lML7YFJJy"

client = ossapi.Ossapi(client_id=CLIENT_ID, client_secret=API_KEY)

PACKS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "packs.json")

# Load existing packs
data = []
existing_tags = set()
max_pack_number = 0

if os.path.exists(PACKS_PATH):
    with open(PACKS_PATH, "r") as f:
        data = json.load(f)
        for entry in data:
            tag = entry.get("packName", "")
            existing_tags.add(tag)
            match = re.match(r"S(\d+)", tag)
            if match:
                num = int(match.group(1))
                if num > max_pack_number:
                    max_pack_number = num

# Start fetching from the next pack number
current_pack_number = max_pack_number + 1

while True:
    pack_tag = f"S{current_pack_number}"
    if pack_tag in existing_tags:
        print(f"{pack_tag} already in packs.json, stopping.")
        break

    try:
        pack = client.beatmap_pack(pack_tag)

        beatmaps = []
        for beatmapset in pack.beatmapsets:
            for beatmap in client.beatmapset(beatmapset.id).beatmaps:
                if beatmap.mode_int != 0:
                    continue
                beatmaps.append({
                    'beatmap_id': beatmap.id,
                    'time_duration_seconds': beatmap.hit_length
                })

        data.append({
            "packName": pack.tag,
            "beatmaps": beatmaps,
            "timestamp": datetime.fromisoformat(pack.date).timestamp()
        })

        print(f"Added pack {pack.tag}")
        data.sort(key=lambda x: x['timestamp'], reverse=True)

        # Ensure directory exists before writing
        dir_path = os.path.dirname(PACKS_PATH)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(PACKS_PATH, "w") as f:
            json.dump(data, f, indent=4)

        time.sleep(0.5)
        current_pack_number += 1

    except Exception as e:
        print(f"Error fetching {pack_tag}: {str(e)}")
        break
