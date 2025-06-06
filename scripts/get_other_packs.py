from ossapi import BeatmapPackType, BeatmapPack
from datetime import datetime

import ossapi
import json
import time

# Your client credentials
CLIENT_ID = 31586
API_KEY = "Sty09gmsufGNjadWZyhNftashebxHV7lML7YFJJy"
BLACKLIST = ["mania", "ctb", "taiko", "catch"]
JSON_PATH = "other_packs.json"

client = ossapi.Ossapi(client_id=CLIENT_ID, client_secret=API_KEY)

# Get beatmap data from a beatmap pack
def get_beatmaps(pack: BeatmapPack):
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
    return beatmaps
        
# Get beatmap packs from a category
def get_category_packs(category: BeatmapPackType, existing_packs: list):
    cursor = None
    packs = existing_packs
    to_skip = list()
    for pack in existing_packs:
        to_skip.append(pack['packname'])

    while True:
        api_packs = client.beatmap_packs(type=category, cursor_string=cursor)
        if not api_packs.beatmap_packs:
            break
        for pack in api_packs.beatmap_packs:
            skip = False
            if pack.tag in to_skip:
                skip = True
            for blacklist in BLACKLIST:
                if blacklist in pack.name.lower():
                    skip = True
                    break
            if skip:
                continue
            pack = client.beatmap_pack(pack.tag)
            beatmaps = get_beatmaps(pack)

            if not len(beatmaps):
                continue

            print(f"Added {pack.tag} ({len(beatmaps)} beatmaps)")

            packs.append({
                "packtag": pack.tag,
                "packname": pack.name,
                "beatmaps": beatmaps,
                "timestamp": datetime.fromisoformat(pack.date).timestamp()
            })
        if not api_packs.cursor:
            break
        cursor = api_packs.cursor
        time.sleep(0.5)
        break
    packs.sort(key=lambda x: x['timestamp'], reverse=True)
    return packs

def main():
    data = {}
    try:
        with open(JSON_PATH) as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading {JSON_PATH}: {str(e)}")
    for category in BeatmapPackType:
        if category.value == "standard":
            continue
        print(f"Fetching {category.value} packs")
        data[category.value] = get_category_packs(category, data[category.value] if category.value in data else [])
    with open(JSON_PATH, "w") as f:
        json.dump(data, f, indent=4)
    
if __name__ == "__main__":
    main()