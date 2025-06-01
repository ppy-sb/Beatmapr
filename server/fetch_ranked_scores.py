import requests
import asyncio
import aiohttp
import time
import ujson
import sys
import os

# Retry logic with exponential backoff
def retry_with_backoff(func, max_retries=3):
    def wrapper(*args, **kwargs):
        retries = 0
        backoff = 1
        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except requests.RequestException as e:
                retries += 1
                print(f"Error occurred: {e}. Retrying in {backoff} seconds...")
                time.sleep(backoff)
                backoff *= 2
        raise Exception(f"Failed after {max_retries} retries.")
    return wrapper

@retry_with_backoff
def fetch_page(user_id, page):
    url = f"https://akatsuki.gg/api/v1/users/scores/best?mode=0&p={page}&l=100&rx=1&id={user_id}"
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()

async def fetch_page_async(session, user_id, page, page_counter):
    url = f"https://akatsuki.gg/api/v1/users/scores/best?mode=0&p={page}&l=100&rx=1&id={user_id}"
    headers = {"Accept-Encoding": "gzip"}
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            page_counter[0] += 1
            print(f"Fetched page: {page}")
            return await response.text()
        else:
            print(f"Error: {response.status}")
            return None

async def fetch_all_pages_async(user_id, start_page, page_counter):
    all_scores = []
    page = start_page

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=5)) as session:
        while True:
            url = f"https://akatsuki.gg/api/v1/users/scores/best?mode=0&p={page}&l=100&rx=1&id={user_id}"
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        print(f"Page {page} failed with status {response.status}")
                        break

                    data = await response.json()
                    scores = data.get("scores")

                    if not scores:
                        print(f"Page {page} returned no scores (scores={scores})")
                        break

                    all_scores.extend(scores)
                    page_counter[0] += 1
                    print(f"Page {page}: {len(scores)} scores (total: {len(all_scores)})")

                    if len(scores) < 100:
                        break

            except Exception as e:
                print(f"Exception on page {page}: {e}")
                break

            page += 1

    return all_scores



def fetch_scores(user_id):
    all_scores = []
    page = 1
    pages_fetched = [0]
    start_time = time.time()

    first_page_data = fetch_page(user_id, page)
    scores = first_page_data.get("scores", [])
    all_scores.extend(scores)
    pages_fetched[0] += 1
    print(f"Fetched page: {page}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    additional_scores = loop.run_until_complete(fetch_all_pages_async(user_id, page + 1, pages_fetched))
    all_scores.extend(additional_scores)
    print(f"Total time: {time.time() - start_time:.2f}s")
    return all_scores, pages_fetched[0]

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

# ===========================
# 🧠 Script Entry Point
# ===========================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_ranked_scores.py <user_id>")
        sys.exit(1)

    user_id = int(sys.argv[1])
    scores, total_pages_fetched = fetch_scores(user_id)

    # Save to /data/{user_id}_scores.txt
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    os.makedirs(output_dir, exist_ok=True)
    output_filename = os.path.join(output_dir, f"{user_id}_scores.txt")

    write_scores_to_file(scores, output_filename)

    print(f"[OK] Scores written to {output_filename}. Pages fetched: {total_pages_fetched}.")
    beatmap_ids = read_beatmap_ids_from_file(output_filename)
    print(f"{len(beatmap_ids)} beatmap IDs loaded from file.")
