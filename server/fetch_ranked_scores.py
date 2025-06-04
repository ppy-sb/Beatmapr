import requests
import asyncio
import aiohttp
import time
import ujson
import json
import sys
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

async def fetch_page_async(session, user_id, page):
    url = f"https://akatsuki.gg/api/v1/users/scores/best?mode=0&p={page}&l=100&rx=1&id={user_id}"
    headers = {"Accept-Encoding": "gzip"}
    try:
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status == 200:
                print(f"✅ Page {page}")
                return await response.text()
            else:
                print(f"Page {page} failed with status {response.status}")
                return None
    except Exception as e:
        print(f"Exception on page {page}: {e}")
        return None

async def fetch_all_pages(user_id):
    all_scores = []
    page = 1
    batch_size = 3
    pages_fetched = 0

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=10)) as session:
        while True:
            tasks = [fetch_page_async(session, user_id, page + i) for i in range(batch_size)]
            responses = await asyncio.gather(*tasks)

            got_more = False

            for i, response in enumerate(responses):
                current_page = page + i
                if response:
                    try:
                        data = ujson.loads(response)
                        scores = data.get("scores", [])
                        if scores:
                            all_scores.extend(scores)
                            pages_fetched += 1
                            print(f"Page {current_page}: {len(scores)} scores (total: {len(all_scores)})")
                            if len(scores) == 100:
                                got_more = True
                    except Exception as e:
                        print(f"Failed to parse page {current_page}: {e}")

            page += batch_size
            if not got_more:
                break

    return all_scores, pages_fetched

def write_scores_to_file(scores, filename):
    rank_counts = {r: 0 for r in ["SSH", "SH", "SS", "S", "A", "B", "C", "D"]}
    total_scores = len(scores)
    total_score_value = 0

    with open(filename, 'w', encoding='utf-8') as file:
        for score in scores:
            beatmap_id = score["beatmap"]["beatmap_id"]
            rank = score["rank"]
            score_value = score["score"]
            total_score_value += score_value
            if str(beatmap_id).isdigit():
                file.write(f"{beatmap_id}\n")
            if rank in rank_counts:
                rank_counts[rank] += 1

        average_score = total_score_value / total_scores if total_scores > 0 else 0
        file.write(f"Total scores: {total_scores}\n")
        file.write(f"Average score: {average_score:.2f}\n")
        file.write(f"SSH: {rank_counts['SSH']}, SH: {rank_counts['SH']}, SS: {rank_counts['SS']}, "
                   f"S: {rank_counts['S']}, A: {rank_counts['A']}, B: {rank_counts['B']}, "
                   f"C: {rank_counts['C']}, D: {rank_counts['D']}\n")

def read_beatmap_ids_from_file(filename):
    beatmap_ids = []
    with open(filename, 'r') as file:
        for line in file:
            line = line.strip()
            if line.isdigit():
                beatmap_ids.append(int(line))
    return beatmap_ids
    print(f"[DEBUG] Beatmap IDs read: {len(beatmap_ids)}")
    print(f"[DEBUG] Unique: {len(set(beatmap_ids))}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_ranked_scores.py <user_id>")
        sys.exit(1)

    user_id = int(sys.argv[1])
    start = time.time()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    scores, page_count = loop.run_until_complete(fetch_all_pages(user_id))

    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    os.makedirs(output_dir, exist_ok=True)
    output_filename = os.path.join(output_dir, f"{user_id}_scores.txt")

    write_scores_to_file(scores, output_filename)
    print(f"[OK] Written to {output_filename}. Pages: {page_count}. Total time: {time.time() - start:.2f}s")

    # Read beatmap IDs as done in frontend logic
    beatmap_ids = []
    with open(output_filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.isdigit():
                beatmap_ids.append(int(line))
    beatmap_ids = list(set(beatmap_ids))  # remove duplicates just in case
    print(f"Loaded {len(beatmap_ids)} beatmap IDs")

    # Load all pack beatmap IDs
    packs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "packs.json"))
    with open(packs_path, "r", encoding="utf-8") as f:
        packs = ujson.load(f)

    all_pack_ids = set()
    for pack in packs:
        for bm in pack["beatmaps"]:
            all_pack_ids.add(int(bm["beatmap_id"]))

    # Count how many maps the user cleared
    cleared = len(set(beatmap_ids) & all_pack_ids)
    total = len(all_pack_ids)
    percent = (cleared / total) * 100 if total > 0 else 0

    # Update users.json
    users_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "users.json"))
    with open(users_path, "r", encoding="utf-8") as f:
        users = json.load(f)

    for user in users:
        if str(user["id"]) == str(user_id):
            user["cleared_beatmaps"] = cleared
            user["completion_percent"] = round(percent, 2)
            user["last_updated"] = datetime.now(ZoneInfo("Europe/London")).strftime("%d/%m/%Y %H:%M")
            break

    with open(users_path, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

    print(f"Updated users.json with cleared_beatmaps={cleared} and completion_percent={percent:.2f}%")

