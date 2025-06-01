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

PACKS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "packs.json")
PACKS_PATH = os.path.abspath(PACKS_PATH)

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
            set_data = client.beatmapset(beatmapset.id)
            for beatmap in set_data.beatmaps:
                if beatmap.mode_int != 0:
                    continue
                beatmaps.append({
                    'beatmap_id': beatmap.id,
                    'beatmapset_id': beatmap.beatmapset_id,
                    'title': set_data.title,
                    'artist': set_data.artist,
                    'version': beatmap.version,
                    'mode_int': beatmap.mode_int,
                    'time_duration_seconds': beatmap.hit_length,
                    'total_length_seconds': beatmap.total_length,
                    'bpm': beatmap.bpm,
                    'cs': beatmap.cs,
                    'ar': beatmap.ar,
                    'od': beatmap.accuracy,
                    'hp': beatmap.drain,
                    'star_rating': round(beatmap.difficulty_rating, 2),
                    'circle_count': beatmap.count_circles,
                    'slider_count': beatmap.count_sliders,
                    'spinner_count': beatmap.count_spinners,
                    'max_combo': beatmap.max_combo,
                    'ranked_status': beatmap.status.name
                })

        data.append({
            "packName": pack.tag,
            "beatmaps": beatmaps,
            "timestamp": datetime.fromisoformat(pack.date).timestamp()
        })

        print(f"✅ Added {pack.tag} ({len(beatmaps)} beatmaps)")

        data.sort(key=lambda x: x['timestamp'], reverse=True)

        os.makedirs(os.path.dirname(PACKS_PATH), exist_ok=True)
        with open(PACKS_PATH, "w") as f:
            json.dump(data, f, indent=4)

        time.sleep(0.5)
        current_pack_number += 1

    except Exception as e:
        print(f"❌ Error fetching {pack_tag}: {str(e)}")
        break
